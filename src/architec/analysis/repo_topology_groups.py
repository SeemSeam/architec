from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from architec.integration.hippo_adapter import HippoSnapshot
from architec.support.io_utils import normalize_relpath, utc_now_iso
from architec.analysis.repo_topology_group_terms import (
    group_folder_votes,
    group_terms,
    module_import_signals,
    secondary_token_share,
)


def path_descriptor_map(
    descriptors: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for descriptor in descriptors.values():
        if not isinstance(descriptor, dict):
            continue
        for path in descriptor.get('files', []):
            norm = normalize_relpath(str(path or ''))
            if norm:
                out[norm] = descriptor
    return out


def group_record(
    *,
    snapshot: HippoSnapshot,
    group_id: str,
    files: list[str],
    path_to_descriptor: dict[str, dict[str, Any]],
    term_generic: set[str],
    stem_tokens_fn,
    tokenize_symbol_fn,
    file_folder_vote_fn,
    preferred_folder_name_fn,
) -> dict[str, Any]:
    evidence_terms, symbols, summaries = group_terms(
        snapshot,
        files,
        path_to_descriptor=path_to_descriptor,
        term_generic=term_generic,
        stem_tokens_fn=stem_tokens_fn,
        tokenize_symbol_fn=tokenize_symbol_fn,
    )
    folder_votes = group_folder_votes(
        files,
        path_to_descriptor=path_to_descriptor,
        file_folder_vote_fn=file_folder_vote_fn,
    )
    recommended_name, alternatives = preferred_folder_name_fn(group_id, evidence_terms)
    if folder_votes:
        dominant_folder, dominant_count = sorted(
            folder_votes.items(),
            key=lambda item: (-item[1], item[0]),
        )[0]
        if dominant_count >= max(2, len(files) // 2):
            recommended_name = dominant_folder
            alternatives = [dominant_folder] + [
                name for name in alternatives
                if name != dominant_folder
            ]
    cohesion = secondary_token_share(files, stem_tokens_fn=stem_tokens_fn)
    folder_share = 1.0
    if folder_votes:
        folder_share = max(folder_votes.values()) / max(1, len(files))
    mixed = (
        (len(files) >= 5 and cohesion < 0.45)
        or (len(folder_votes) >= 2 and folder_share < 0.8)
    )
    return {
        'group_id': group_id,
        'file_count': len(files),
        'candidate_files': files[:12],
        'evidence_terms': evidence_terms,
        'primary_symbols': symbols,
        'responsibility_summary': ' '.join(summaries).strip(),
        'programmatic_name': recommended_name,
        'alternative_names': alternatives[:3],
        'folder_votes': folder_votes,
        'status': 'mixed' if mixed else 'cohesive',
        'cohesion': round(cohesion, 2),
        'folder_share': round(folder_share, 2),
    }


def domain_groups(
    snapshot: HippoSnapshot,
    direct_files: list[str],
    *,
    path_to_descriptor: dict[str, dict[str, Any]],
    domain_token_fn,
    term_generic: set[str],
    stem_tokens_fn,
    tokenize_symbol_fn,
    file_folder_vote_fn,
    preferred_folder_name_fn,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for path in direct_files:
        stem = Path(path).stem
        if stem.startswith('__'):
            continue
        grouped[domain_token_fn(path)].append(path)

    records = [
        group_record(
            snapshot=snapshot,
            group_id=group_id,
            files=sorted(paths),
            path_to_descriptor=path_to_descriptor,
            term_generic=term_generic,
            stem_tokens_fn=stem_tokens_fn,
            tokenize_symbol_fn=tokenize_symbol_fn,
            file_folder_vote_fn=file_folder_vote_fn,
            preferred_folder_name_fn=preferred_folder_name_fn,
        )
        for group_id, paths in grouped.items()
        if len(paths) >= 2
    ]
    records.sort(
        key=lambda item: (
            -int(item.get('file_count', 0) or 0),
            str(item.get('group_id', '')),
        )
    )
    return records


def build_review(
    *,
    source_root: str,
    direct_files: list[str],
    compat_wrappers: list[str],
    subpackage_total: int,
    peer_directories: list[str],
    flatness_score: float,
    placement_review: dict[str, Any],
    folder_membership_review: dict[str, Any],
    findings: list[dict[str, Any]],
    groups: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        'generated_at': utc_now_iso(),
        'source_root': source_root,
        'flat_file_total': len(direct_files),
        'compat_wrapper_total': len(compat_wrappers),
        'compat_wrappers': compat_wrappers[:16],
        'subpackage_total': subpackage_total,
        'peer_directories': peer_directories,
        'flatness_score': flatness_score,
        'needs_folder_management': bool(len(direct_files) >= 12 and subpackage_total == 0),
        'summary': (
            f'{source_root} has {len(direct_files)} direct Python modules '
            f'across {len(groups)} implicit domain groups.'
            if source_root
            else 'No dominant source root detected for folder review.'
        ),
        'root_placement_review': placement_review,
        'folder_membership_review': folder_membership_review,
        'findings': findings,
        'groups': groups,
    }
