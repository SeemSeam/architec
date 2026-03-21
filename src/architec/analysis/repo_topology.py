from __future__ import annotations

from pathlib import Path
from typing import Any

from .analysis_cache import run_cached_analysis
from .repo_topology_groups import (
    build_review as build_review_impl,
    domain_groups as domain_groups_impl,
    group_folder_votes as group_folder_votes_impl,
    module_import_signals as module_import_signals_impl,
    path_descriptor_map as path_descriptor_map_impl,
)
from .repo_topology_migration import build_migration_plan
from .repo_topology_llm import (
    apply_llm_reviews as apply_llm_reviews_impl,
    llm_topology_review as llm_topology_review_impl,
)
from .repo_topology_paths import (
    compat_wrapper_paths as compat_wrapper_paths_impl,
    direct_module_paths as direct_module_paths_impl,
    flatness_score as flatness_score_impl,
    peer_directories as peer_directories_impl,
    python_files as python_files_impl,
    source_root as source_root_impl,
)
from .repo_topology_review_helpers import (
    folder_membership_review as folder_membership_review_impl,
    placement_review as placement_review_impl,
    topology_findings as topology_findings_impl,
)
from .repo_topology_rules import (
    FILE_FOLDER_HINTS,
    TERM_GENERIC,
    domain_token as _domain_token,
    file_folder_vote as _file_folder_vote,
    preferred_folder_name as _preferred_folder_name,
    stem_tokens as _stem_tokens,
    tokenize_symbol as _tokenize_symbol,
    descriptor_terms_for_path as _descriptor_terms_for_path,
)
from ..descriptors.public import load_or_build_component_descriptors
from ..integration.hippo_adapter import HippoSnapshot
from ..support.io_utils import normalize_relpath, utc_now_iso, write_json
from ..support.llm_guard import guard_llm_result
from ..integration.paths import TOPOLOGY_REVIEW_PATH
from ..backend_llm import complete_json
_ROOT_KEEP_FILENAMES = {'__init__.py', '__main__.py', 'cli.py'}
_ROOT_FACADE_STEMS = {
    'analysis_runner',
    'backend_llm',
    'component_descriptors',
    'orchestrator',
    'scoring_policy',
}
_TERM_GENERIC = {
    'architec',
    'component',
    'module',
    'system',
    'helper',
    'helpers',
    'core',
    'common',
    'shared',
    'misc',
    'utils',
    'python',
    'file',
    'files',
}


def _placement_review(
    *,
    project_root: Path,
    source_root: str,
    direct_files: list[str],
    groups: list[dict[str, Any]],
    path_to_descriptor: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return placement_review_impl(
        project_root=project_root,
        source_root=source_root,
        direct_files=direct_files,
        groups=groups,
        path_to_descriptor=path_to_descriptor,
        root_keep_filenames=_ROOT_KEEP_FILENAMES,
        root_facade_stems=_ROOT_FACADE_STEMS,
        file_folder_vote_fn=_file_folder_vote,
        module_import_signals_fn=_module_import_signals,
    )


def _folder_membership_review(
    groups: list[dict[str, Any]],
    *,
    path_to_descriptor: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return folder_membership_review_impl(
        groups,
        path_to_descriptor=path_to_descriptor,
        group_folder_votes_fn=_group_folder_votes,
    )


def _topology_findings(
    *,
    source_root: str,
    flat_file_total: int,
    subpackage_total: int,
    groups: list[dict[str, Any]],
    placement_review: dict[str, Any],
    folder_membership_review: dict[str, Any],
) -> list[dict[str, Any]]:
    return topology_findings_impl(
        source_root=source_root,
        flat_file_total=flat_file_total,
        subpackage_total=subpackage_total,
        groups=groups,
        placement_review=placement_review,
        folder_membership_review=folder_membership_review,
    )


def _llm_topology_review(project_root: Path, review: dict[str, Any]) -> dict[str, Any] | None:
    return llm_topology_review_impl(
        project_root,
        review,
        run_cached_analysis_fn=run_cached_analysis,
        guard_llm_result_fn=guard_llm_result,
        complete_json_fn=complete_json,
    )


def _apply_llm_reviews(review: dict[str, Any], llm_part: dict[str, Any] | None) -> None:
    apply_llm_reviews_impl(review, llm_part)


def review_folder_topology(
    project_root: str | Path,
    *,
    snapshot: HippoSnapshot | None = None,
    llm_enabled: bool = True,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    snap = snapshot or HippoSnapshot.load(root)
    py_files = python_files_impl(snap)
    source_root = source_root_impl(py_files)
    raw_direct_files = direct_module_paths_impl(py_files, source_root)
    compat_wrappers = compat_wrapper_paths_impl(root, raw_direct_files)
    compat_wrapper_set = set(compat_wrappers)
    direct_files = [path for path in raw_direct_files if path not in compat_wrapper_set]
    subpackage_total = len(peer_directories_impl(source_root, root))
    descriptors = load_or_build_component_descriptors(root, snapshot=snap, persist=False)
    path_to_descriptor = path_descriptor_map_impl(descriptors)
    groups = domain_groups_impl(
        snap,
        direct_files,
        path_to_descriptor=path_to_descriptor,
        domain_token_fn=_domain_token,
        term_generic=_TERM_GENERIC,
        stem_tokens_fn=_stem_tokens,
        tokenize_symbol_fn=_tokenize_symbol,
        file_folder_vote_fn=_file_folder_vote,
        preferred_folder_name_fn=_preferred_folder_name,
    )
    placement_review = _placement_review(
        project_root=root,
        source_root=source_root,
        direct_files=direct_files,
        groups=groups,
        path_to_descriptor=path_to_descriptor,
    )
    folder_membership_review = _folder_membership_review(
        groups,
        path_to_descriptor=path_to_descriptor,
    )
    flatness_score = flatness_score_impl(
        flat_file_total=len(direct_files),
        subpackage_total=subpackage_total,
        grouped_total=len(groups),
    )

    review = build_review_impl(
        source_root=source_root,
        direct_files=direct_files,
        compat_wrappers=compat_wrappers,
        subpackage_total=subpackage_total,
        peer_directories=peer_directories_impl(source_root, root),
        flatness_score=flatness_score,
        placement_review=placement_review,
        folder_membership_review=folder_membership_review,
        findings=_topology_findings(
            source_root=source_root,
            flat_file_total=len(direct_files),
            subpackage_total=subpackage_total,
            groups=groups,
            placement_review=placement_review,
            folder_membership_review=folder_membership_review,
        ),
        groups=groups,
    )
    if llm_enabled and groups:
        llm_part = _llm_topology_review(root, review)
        if llm_part:
            _apply_llm_reviews(review, llm_part)
            review['llm_topology_review'] = llm_part
            review['llm_naming_review'] = llm_part
    review['migration_plan'] = build_migration_plan(
        source_root=source_root,
        direct_files=direct_files,
        groups=groups,
        placement_review=placement_review,
        llm_topology_review=review.get('llm_topology_review') if isinstance(review.get('llm_topology_review'), dict) else None,
    )

    write_json(root / TOPOLOGY_REVIEW_PATH, review)
    return review


def _group_folder_votes(
    files: list[str],
    *,
    path_to_descriptor: dict[str, dict[str, Any]],
) -> dict[str, int]:
    return group_folder_votes_impl(
        files,
        path_to_descriptor=path_to_descriptor,
        file_folder_vote_fn=_file_folder_vote,
    )


def _module_import_signals(project_root: Path, path: str, source_root: str) -> dict[str, Any]:
    return module_import_signals_impl(project_root, path, source_root)
