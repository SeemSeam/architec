from __future__ import annotations

from collections import Counter
from typing import Any

from ..descriptors.public import descriptor_search_text, load_or_build_component_descriptors
from ..scoring.component_selection_policy import (
    is_infra_component,
    query_targets_infra,
    query_targets_tests,
)
from ..integration.hippo_adapter import HippoSnapshot


def _resolve_preferred_component(
    components: list[str],
    comp_files: dict[str, list[str]],
    preferred: str | None,
) -> str:
    if not preferred:
        return ""
    pref = preferred.strip()
    if pref in comp_files:
        return pref
    for component in components:
        if pref.lower() in component.lower():
            return component
    return ""


def _component_name_scores(components: list[str], question_low: str) -> Counter[str]:
    scores: Counter[str] = Counter()
    for component in components:
        comp_low = component.lower()
        if comp_low in question_low:
            scores[component] += 10
        for token in comp_low.replace(":", "/").split("/"):
            if len(token) >= 3 and token in question_low:
                scores[component] += 4
    return scores


def _descriptor_scores(
    descriptors: dict[str, dict[str, Any]],
    question_low: str,
) -> Counter[str]:
    scores: Counter[str] = Counter()
    question_tokens = {
        token.strip().lower()
        for token in question_low.replace(":", " ").replace("/", " ").split()
        if len(token.strip()) >= 4
    }
    for component, descriptor in descriptors.items():
        search_text = descriptor_search_text(descriptor).lower()
        confidence = float(descriptor.get("confidence", 0.0) or 0.0)
        matched = sum(1 for token in question_tokens if token in search_text)
        if matched > 0:
            scores[component] += matched * 3 + int(round(confidence * 3))
    return scores


def _path_scores(snapshot: HippoSnapshot, question_low: str) -> Counter[str]:
    scores: Counter[str] = Counter()
    question_tokens = [token for token in question_low.split() if len(token) >= 3]
    for path in snapshot.first_party_paths():
        low = path.lower()
        component = snapshot.component_for_path(path)
        if low in question_low:
            scores[component] += 15
        elif any(token in low for token in question_tokens):
            scores[component] += 1
    return scores


def _merge_scores(*score_sets: Counter[str]) -> Counter[str]:
    merged: Counter[str] = Counter()
    for score_set in score_sets:
        merged.update(score_set)
    return merged


def _apply_selection_penalties(
    scores: Counter[str],
    *,
    mentions_tests: bool,
    mentions_infra: bool,
    descriptors: dict[str, dict[str, Any]],
) -> None:
    if not mentions_tests:
        for component in list(scores.keys()):
            if str(component).endswith(":tests"):
                scores[component] -= 6
    if not mentions_infra:
        for component in list(scores.keys()):
            if is_infra_component(component, descriptors.get(component, {})):
                scores[component] -= 7


def _allowed_component(
    component: str,
    *,
    mentions_tests: bool,
    mentions_infra: bool,
    descriptors: dict[str, dict[str, Any]],
) -> bool:
    if not mentions_tests and str(component).endswith(":tests"):
        return False
    if not mentions_infra and is_infra_component(component, descriptors.get(component, {})):
        return False
    return True


def _fallback_component(
    components: list[str],
    comp_files: dict[str, list[str]],
    *,
    mentions_tests: bool,
    mentions_infra: bool,
    descriptors: dict[str, dict[str, Any]],
) -> str:
    if not components:
        return "unknown"
    filtered = [
        component
        for component in components
        if _allowed_component(
            component,
            mentions_tests=mentions_tests,
            mentions_infra=mentions_infra,
            descriptors=descriptors,
        )
    ]
    if filtered:
        return max(filtered, key=lambda component: len(comp_files.get(component, [])))
    return max(components, key=lambda component: len(comp_files.get(component, [])))


def infer_component(snapshot: HippoSnapshot, question: str, preferred: str | None = None) -> str:
    comp_files = snapshot.component_files()
    components = list(comp_files.keys())
    descriptors = load_or_build_component_descriptors(
        snapshot.project_root,
        snapshot=snapshot,
        persist=False,
    )
    preferred_component = _resolve_preferred_component(components, comp_files, preferred)
    if preferred_component:
        return preferred_component

    question_low = (question or "").lower()
    mentions_tests = query_targets_tests(question_low)
    mentions_infra = query_targets_infra(question_low)
    scores = _merge_scores(
        _component_name_scores(components, question_low),
        _descriptor_scores(descriptors, question_low),
        _path_scores(snapshot, question_low),
    )
    _apply_selection_penalties(
        scores,
        mentions_tests=mentions_tests,
        mentions_infra=mentions_infra,
        descriptors=descriptors,
    )
    if scores:
        for component, _score in scores.most_common():
            if _allowed_component(
                component,
                mentions_tests=mentions_tests,
                mentions_infra=mentions_infra,
                descriptors=descriptors,
            ):
                return component
        return scores.most_common(1)[0][0]
    return _fallback_component(
        components,
        comp_files,
        mentions_tests=mentions_tests,
        mentions_infra=mentions_infra,
        descriptors=descriptors,
    )
