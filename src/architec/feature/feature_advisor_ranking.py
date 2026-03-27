from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

from ..scoring.component_selection_policy import (
    query_targets_infra,
    query_targets_tests,
)
from ..support.path_policy import is_relevant_arch_path as shared_is_relevant_arch_path, is_test_like_path
from .feature_advisor_ranking_phase1 import (
    apply_descriptor_scores,
    apply_penalties,
    apply_token_symbol_scores,
    build_searchable_documents,
)
from .feature_advisor_ranking_output import build_ranked_output
from .feature_advisor_ranking_phase2 import apply_hint_component_hotspot_scores
from .feature_query import build_goal_signals


def rank_candidate_files(
    snapshot,
    goal: str,
    *,
    descriptor_loader: Callable[..., dict[str, dict[str, Any]]],
    top_n: int = 20,
) -> list[dict[str, Any]]:
    def is_relevant_arch_path(path: str) -> bool:
        checker = getattr(snapshot, "is_architecture_path", None)
        if callable(checker):
            return bool(checker(path))
        return shared_is_relevant_arch_path(path)

    project_root = Path(getattr(snapshot, "project_root", Path("."))).resolve()
    descriptors = descriptor_loader(
        project_root,
        snapshot=snapshot,
        persist=False,
    )
    allow_infra = query_targets_infra(goal)
    allow_tests = query_targets_tests(goal)
    searchable_documents = build_searchable_documents(
        snapshot=snapshot,
        descriptors=descriptors,
        is_relevant_arch_path=is_relevant_arch_path,
    )
    signals = build_goal_signals(goal, searchable_documents=searchable_documents)
    file_scores: Counter[str] = Counter()
    evidence: dict[str, set[str]] = defaultdict(set)
    apply_token_symbol_scores(
        snapshot=snapshot,
        weighted_tokens=signals.weighted_tokens,
        file_scores=file_scores,
        evidence=evidence,
        is_relevant_arch_path=is_relevant_arch_path,
    )
    apply_descriptor_scores(
        snapshot=snapshot,
        descriptors=descriptors,
        weighted_tokens=signals.weighted_tokens,
        file_scores=file_scores,
        evidence=evidence,
        is_relevant_arch_path=is_relevant_arch_path,
    )
    apply_penalties(
        snapshot=snapshot,
        descriptors=descriptors,
        file_scores=file_scores,
        evidence=evidence,
        allow_infra=allow_infra,
        allow_tests=allow_tests,
        is_test_like_path=is_test_like_path,
    )
    apply_hint_component_hotspot_scores(
        snapshot=snapshot,
        signals=signals,
        file_scores=file_scores,
        evidence=evidence,
        is_relevant_arch_path=is_relevant_arch_path,
    )
    return build_ranked_output(
        snapshot=snapshot,
        file_scores=file_scores,
        evidence=evidence,
        top_n=top_n,
    )
