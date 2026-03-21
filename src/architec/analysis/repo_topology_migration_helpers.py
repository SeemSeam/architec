from __future__ import annotations

from typing import Any

from architec.support.io_utils import normalize_relpath


def _topology_review(group: dict[str, Any]) -> dict[str, Any]:
    review = group.get('topology_review', {})
    return review if isinstance(review, dict) else {}


def _naming_review(group: dict[str, Any]) -> dict[str, Any]:
    review = group.get('naming_review', {})
    return review if isinstance(review, dict) else {}


def _resolved_recommendation(group: dict[str, Any]) -> tuple[str, str, float, str] | None:
    for review, source in ((_topology_review(group), 'llm'), (_naming_review(group), 'llm')):
        recommended = str(
            review.get('recommended_folder', '')
            or review.get('recommended_name', '')
            or ''
        ).strip()
        if recommended:
            return (
                recommended,
                source,
                float(review.get('confidence', 0.0) or 0.0),
                str(review.get('decision', '') or 'review'),
            )
    return None


def resolved_group_folder(group: dict[str, Any]) -> tuple[str, str, float, str]:
    resolved = _resolved_recommendation(group)
    if resolved is not None:
        return resolved
    return (
        str(group.get('programmatic_name', '') or '').strip(),
        'programmatic',
        0.0,
        'accept',
    )


def llm_file_reviews(llm_topology_review: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(llm_topology_review, dict):
        return {}
    raw = llm_topology_review.get('file_reviews', [])
    if not isinstance(raw, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        path = normalize_relpath(str(item.get('path', '') or ''))
        if path:
            out[path] = item
    return out


def _base_placement(path: str, placement_review: dict[str, Any]) -> dict[str, Any]:
    base = (
        placement_review.get('by_path', {}).get(path, {})
        if isinstance(placement_review.get('by_path', {}), dict)
        else {}
    )
    return base if isinstance(base, dict) else {}


def _fallback_placement(base: dict[str, Any]) -> dict[str, Any]:
    alternatives = base.get('alternative_folders', [])
    return {
        'decision': str(base.get('decision', 'review') or 'review'),
        'folder': str(base.get('programmatic_folder', '') or ''),
        'alternatives': list(alternatives[:3]) if isinstance(alternatives, list) else [],
        'reason': str(base.get('reason', '') or ''),
        'source': 'programmatic',
        'confidence': float(base.get('confidence', 0.0) or 0.0),
    }


def _resolved_alternatives(
    llm_item: dict[str, Any],
    base: dict[str, Any],
) -> list[str]:
    alternatives = [
        str(name or '')
        for name in llm_item.get('alternatives', [])[:3]
        if str(name or '').strip()
    ]
    if not alternatives and isinstance(base.get('alternative_folders', []), list):
        alternatives = list(base.get('alternative_folders', [])[:3])
    return alternatives


def _llm_placement(llm_item: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
    keep_root = bool(llm_item.get('keep_root', False))
    folder = str(
        llm_item.get('recommended_folder', '')
        or base.get('programmatic_folder', '')
        or ''
    ).strip()
    decision = (
        'keep_root'
        if keep_root
        else str(llm_item.get('decision', '') or '').strip()
        or str(base.get('decision', 'review') or 'review')
    )
    return {
        'decision': decision,
        'folder': folder,
        'alternatives': _resolved_alternatives(llm_item, base),
        'reason': str(llm_item.get('reason', '') or base.get('reason', '') or ''),
        'source': 'llm',
        'confidence': float(
            llm_item.get('confidence', 0.0)
            or base.get('confidence', 0.0)
            or 0.0
        ),
    }


def effective_file_placement(
    path: str,
    *,
    placement_review: dict[str, Any],
    llm_file_reviews_by_path: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    base = _base_placement(path, placement_review)
    llm_item = llm_file_reviews_by_path.get(path, {})
    if not isinstance(llm_item, dict) or not llm_item:
        return _fallback_placement(base)
    return _llm_placement(llm_item, base)


def _phase_payload(
    *,
    phase: str,
    goal: str,
    folders: list[str],
    extra_key: str,
    extra_value: Any,
) -> dict[str, Any]:
    payload = {
        'phase': phase,
        'goal': goal,
        'folders': folders[:8],
    }
    payload[extra_key] = extra_value
    return payload


def _sorted_folder_plans(folder_plans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    folder_plans.sort(
        key=lambda item: (
            -int(item.get('file_count', 0) or 0),
            str(item.get('folder', '')),
        )
    )
    return folder_plans


def _sorted_moves(file_moves: list[dict[str, Any]]) -> list[dict[str, Any]]:
    file_moves.sort(key=lambda item: (str(item.get('folder', '')), str(item.get('from', ''))))
    return file_moves


def _phase_groups(folder_plans: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    large_cohesive = [
        item
        for item in folder_plans
        if str(item.get('status', '')) == 'cohesive'
        and int(item.get('file_count', 0) or 0) >= 3
    ]
    mixed_or_small = [item for item in folder_plans if item not in large_cohesive]
    return large_cohesive, mixed_or_small


def _migration_phases(
    *,
    folders_to_create: list[str],
    retained_root_files: list[dict[str, Any]],
    review_files: list[dict[str, Any]],
    large_cohesive: list[dict[str, Any]],
    mixed_or_small: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        _phase_payload(
            phase='P0',
            goal='Create target folders and preserve compatibility facades at package root.',
            folders=folders_to_create,
            extra_key='root_retained_files',
            extra_value=[item['path'] for item in retained_root_files[:8]],
        ),
        _phase_payload(
            phase='P1',
            goal='Move largest cohesive file families first.',
            folders=[item['folder'] for item in large_cohesive],
            extra_key='file_total',
            extra_value=sum(int(item.get('file_count', 0) or 0) for item in large_cohesive),
        ),
        _phase_payload(
            phase='P2',
            goal='Resolve mixed groups and singleton support modules.',
            folders=[item['folder'] for item in mixed_or_small],
            extra_key='review_file_total',
            extra_value=len(review_files),
        ),
    ]


def finalize_migration_plan(
    *,
    source_root: str,
    folders_to_create: list[str],
    folder_plans: list[dict[str, Any]],
    file_moves: list[dict[str, Any]],
    retained_root_files: list[dict[str, Any]],
    review_files: list[dict[str, Any]],
) -> dict[str, Any]:
    _sorted_folder_plans(folder_plans)
    _sorted_moves(file_moves)
    review_files.sort(key=lambda item: str(item.get('path', '')))
    retained_root_files.sort(key=lambda item: str(item.get('path', '')))

    large_cohesive, mixed_or_small = _phase_groups(folder_plans)
    return {
        'target_root': source_root,
        'folders_to_create': folders_to_create,
        'folder_plans': folder_plans,
        'file_moves': file_moves,
        'retained_root_files': retained_root_files,
        'review_files': review_files,
        'phases': _migration_phases(
            folders_to_create=folders_to_create,
            retained_root_files=retained_root_files,
            review_files=review_files,
            large_cohesive=large_cohesive,
            mixed_or_small=mixed_or_small,
        ),
        'summary': (
            f"Move {len(file_moves)} files into {len(folders_to_create)} folders, "
            f"keep {len(retained_root_files)} root facades, review {len(review_files)} uncertain files."
        ),
    }
