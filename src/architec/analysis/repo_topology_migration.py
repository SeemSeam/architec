from __future__ import annotations

from pathlib import Path
from typing import Any

from .repo_topology_migration_helpers import (
    effective_file_placement,
    finalize_migration_plan,
    llm_file_reviews,
    resolved_group_folder,
)
from architec.support.io_utils import normalize_relpath


def _folder_plan_entry(group: dict[str, Any], folder: str, naming_source: str, confidence: float, decision: str) -> dict[str, Any]:
    return {
        'group_id': str(group.get('group_id', '') or ''),
        'folder': folder,
        'naming_source': naming_source,
        'confidence': confidence,
        'decision': decision,
        'status': str(group.get('status', '') or ''),
        'file_count': int(group.get('file_count', 0) or 0),
        'files': list(group.get('candidate_files', [])[:12]),
    }


def _retained_root_entry(path: str, placement: dict[str, Any]) -> dict[str, Any]:
    return {
        'path': path,
        'reason': str(
            placement.get('reason', '')
            or 'Keep package-root entrypoint or facade.'
        ),
        'source': str(
            placement.get('source', 'programmatic') or 'programmatic'
        ),
    }


def _group_file_move(
    *,
    path: str,
    source_root: str,
    basename: str,
    group: dict[str, Any],
    placement: dict[str, Any],
    folder: str,
    naming_source: str,
    confidence: float,
) -> dict[str, Any]:
    target = f"{source_root}/{folder}/{basename}" if source_root and folder else path
    return {
        'from': path,
        'to': target,
        'folder': folder,
        'group_id': str(group.get('group_id', '') or ''),
        'reason': str(
            placement.get('reason', '')
            or f"Grouped into implicit domain `{group.get('group_id', '')}`."
        ),
        'naming_source': str(
            placement.get('source', naming_source) or naming_source
        ),
        'confidence': max(
            confidence,
            float(placement.get('confidence', 0.0) or 0.0),
        ),
    }


def _review_file_entry(
    *,
    path: str,
    suggested_folder: str,
    alternatives: list[str],
    reason: str,
    source: str,
) -> dict[str, Any]:
    return {
        'path': path,
        'suggested_folder': suggested_folder,
        'alternative_folders': alternatives,
        'reason': reason,
        'source': source,
    }


def _collect_group_folder_plans(
    groups: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], set[str], dict[str, dict[str, Any]]]:
    file_to_group: dict[str, dict[str, Any]] = {}
    folder_plans: list[dict[str, Any]] = []
    folders_to_create: list[str] = []
    seen_folders: set[str] = set()
    for group in groups:
        if not isinstance(group, dict):
            continue
        folder, naming_source, confidence, decision = resolved_group_folder(group)
        if not folder:
            continue
        if folder not in seen_folders:
            folders_to_create.append(folder)
            seen_folders.add(folder)
        folder_plans.append(
            _folder_plan_entry(group, folder, naming_source, confidence, decision)
        )
        for path in group.get('candidate_files', []):
            norm = normalize_relpath(str(path or ''))
            if norm:
                file_to_group[norm] = group
    return folder_plans, folders_to_create, seen_folders, file_to_group


def _append_group_move_or_review(
    *,
    path: str,
    source_root: str,
    basename: str,
    group: dict[str, Any],
    placement: dict[str, Any],
    file_moves: list[dict[str, Any]],
    review_files: list[dict[str, Any]],
) -> None:
    folder, naming_source, confidence, decision = resolved_group_folder(group)
    if placement.get('folder'):
        folder = str(placement.get('folder', '') or folder)
    if decision in {'split', 'review'} and placement.get('source') != 'llm':
        review_files.append(
            _review_file_entry(
                path=path,
                suggested_folder=folder,
                alternatives=placement.get('alternatives', []),
                reason=(
                    f'Group `{group.get("group_id", "")}` needs explicit review '
                    'before moving files.'
                ),
                source=naming_source,
            )
        )
        return
    file_moves.append(
        _group_file_move(
            path=path,
            source_root=source_root,
            basename=basename,
            group=group,
            placement=placement,
            folder=folder,
            naming_source=naming_source,
            confidence=confidence,
        )
    )


def _append_singleton_move_or_review(
    *,
    path: str,
    source_root: str,
    basename: str,
    placement: dict[str, Any],
    file_moves: list[dict[str, Any]],
    review_files: list[dict[str, Any]],
    folders_to_create: list[str],
    seen_folders: set[str],
) -> None:
    suggested_folder = str(placement.get('folder', '') or '')
    if placement.get('decision') == 'move' and suggested_folder:
        file_moves.append(
            {
                'from': path,
                'to': f"{source_root}/{suggested_folder}/{basename}" if source_root else path,
                'folder': suggested_folder,
                'group_id': '',
                'reason': str(
                    placement.get('reason', '')
                    or 'Move singleton implementation file into its reviewed folder.'
                ),
                'naming_source': str(
                    placement.get('source', 'programmatic') or 'programmatic'
                ),
                'confidence': float(placement.get('confidence', 0.0) or 0.0),
            }
        )
        if suggested_folder not in seen_folders:
            folders_to_create.append(suggested_folder)
            seen_folders.add(suggested_folder)
        return

    review_files.append(
        _review_file_entry(
            path=path,
            suggested_folder=suggested_folder,
            alternatives=placement.get('alternatives', []),
            reason=str(
                placement.get('reason', '')
                or (
                    f"`{Path(path).stem}` is a singleton or weak family under "
                    f'{source_root} and needs manual placement review.'
                )
            ),
            source=str(placement.get('source', 'programmatic') or 'programmatic'),
        )
    )


def build_migration_plan(
    *,
    source_root: str,
    direct_files: list[str],
    groups: list[dict[str, Any]],
    placement_review: dict[str, Any],
    llm_topology_review: dict[str, Any] | None,
) -> dict[str, Any]:
    folder_plans, folders_to_create, seen_folders, file_to_group = (
        _collect_group_folder_plans(groups)
    )
    llm_file_reviews_by_path = llm_file_reviews(llm_topology_review)

    retained_root_files: list[dict[str, Any]] = []
    file_moves: list[dict[str, Any]] = []
    review_files: list[dict[str, Any]] = []

    for path in direct_files:
        basename = Path(path).name
        placement = effective_file_placement(
            path,
            placement_review=placement_review,
            llm_file_reviews_by_path=llm_file_reviews_by_path,
        )
        if placement.get('decision') == 'keep_root':
            retained_root_files.append(_retained_root_entry(path, placement))
            continue

        group = file_to_group.get(path)
        if group is not None:
            _append_group_move_or_review(
                path=path,
                source_root=source_root,
                basename=basename,
                group=group,
                placement=placement,
                file_moves=file_moves,
                review_files=review_files,
            )
            continue

        _append_singleton_move_or_review(
            path=path,
            source_root=source_root,
            basename=basename,
            placement=placement,
            file_moves=file_moves,
            review_files=review_files,
            folders_to_create=folders_to_create,
            seen_folders=seen_folders,
        )

    return finalize_migration_plan(
        source_root=source_root,
        folders_to_create=folders_to_create,
        folder_plans=folder_plans,
        file_moves=file_moves,
        retained_root_files=retained_root_files,
        review_files=review_files,
    )
