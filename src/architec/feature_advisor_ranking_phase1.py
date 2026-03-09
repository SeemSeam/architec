from __future__ import annotations

from typing import Any, Callable

from .component_descriptors import descriptor_search_text
from .component_selection_policy import is_infra_component


def build_searchable_documents(
    *,
    snapshot: Any,
    descriptors: dict[str, dict[str, Any]],
    is_relevant_arch_path: Callable[[str], bool],
) -> list[str]:
    docs: list[str] = []
    for path in snapshot.first_party_paths():
        if not is_relevant_arch_path(path):
            continue
        docs.append(path.lower())
        for sig in snapshot.signatures_for_file(path):
            docs.append(str(sig.get("name", "")).lower())
            docs.append(str(sig.get("parent", "")).lower())
    for descriptor in descriptors.values():
        docs.append(descriptor_search_text(descriptor))
    return docs


def apply_token_symbol_scores(
    *,
    snapshot: Any,
    weighted_tokens: dict[str, float],
    file_scores: Any,
    evidence: dict[str, set[str]],
    is_relevant_arch_path: Callable[[str], bool],
) -> None:
    for path in snapshot.first_party_paths():
        if not is_relevant_arch_path(path):
            continue
        low_path = path.lower()
        for token, weight in weighted_tokens.items():
            if token in low_path:
                file_scores[path] += max(1, round(5 * weight))
                evidence[path].add(f"path:{token}")
        for sig in snapshot.signatures_for_file(path):
            name = str(sig.get("name", "")).lower()
            parent = str(sig.get("parent", "")).lower()
            for token, weight in weighted_tokens.items():
                if token in name or (parent and token in parent):
                    file_scores[path] += max(1, round(3 * weight))
                    evidence[path].add(f"symbol:{token}")


def apply_descriptor_scores(
    *,
    snapshot: Any,
    descriptors: dict[str, dict[str, Any]],
    weighted_tokens: dict[str, float],
    file_scores: Any,
    evidence: dict[str, set[str]],
    is_relevant_arch_path: Callable[[str], bool],
) -> None:
    for component, descriptor in descriptors.items():
        search_text = descriptor_search_text(descriptor).lower()
        confidence = float(descriptor.get("confidence", 0.0) or 0.0)
        matched_terms = [token for token in weighted_tokens if token in search_text]
        if not matched_terms:
            continue
        if len(matched_terms) < 2 and confidence < 0.7:
            continue
        boost = min(8, 2 + len(matched_terms) + int(round(confidence * 2)))
        for path in snapshot.component_files().get(component, [])[:12]:
            if not is_relevant_arch_path(path):
                continue
            file_scores[path] += boost
            evidence[path].add(f"descriptor:{component}")


def apply_penalties(
    *,
    snapshot: Any,
    descriptors: dict[str, dict[str, Any]],
    file_scores: Any,
    evidence: dict[str, set[str]],
    allow_infra: bool,
    allow_tests: bool,
    is_test_like_path: Callable[[str], bool],
) -> None:
    for path in list(file_scores.keys()):
        component = snapshot.component_for_path(path)
        if not allow_infra and is_infra_component(component, descriptors.get(component, {})):
            file_scores[path] = max(0, int(file_scores[path]) - 9)
            evidence[path].add("infra_penalty")
        if not allow_tests and (is_test_like_path(path) or str(component).endswith(":tests")):
            file_scores[path] = max(0, int(file_scores[path]) - 8)
            evidence[path].add("tests_penalty")
