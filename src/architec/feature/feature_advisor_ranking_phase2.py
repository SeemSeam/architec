from __future__ import annotations

from typing import Any, Callable

from ..scoring.contract_engine import aggregate_hotspots
from .feature_query import component_tokens


def apply_hint_scores(
    *,
    snapshot: Any,
    signals: Any,
    file_scores: Any,
    evidence: dict[str, set[str]],
    is_relevant_arch_path: Callable[[str], bool],
) -> None:
    for component, hint_score in signals.hint_scores.items():
        if hint_score <= 0:
            continue
        for path in snapshot.component_files().get(component, []):
            if not is_relevant_arch_path(path):
                continue
            file_scores[path] += int(hint_score)
            evidence[path].add(f"hint:{component}")


def apply_component_token_scores(
    *,
    snapshot: Any,
    signals: Any,
    file_scores: Any,
    evidence: dict[str, set[str]],
    is_relevant_arch_path: Callable[[str], bool],
) -> None:
    for component, files in snapshot.component_files().items():
        matched = [token for token in component_tokens(component) if token in signals.goal_low]
        if not matched:
            continue
        component_boost = 4 if len(matched) >= 2 else 2
        for path in files[:12]:
            if not is_relevant_arch_path(path):
                continue
            file_scores[path] += component_boost
            evidence[path].add(f"component:{component}")


def apply_hotspot_scores(
    *,
    snapshot: Any,
    file_scores: Any,
    evidence: dict[str, set[str]],
) -> None:
    for hotspot in aggregate_hotspots(snapshot.first_party_findings(), top_n=60):
        path = str(hotspot.get("path", ""))
        if path not in file_scores:
            continue
        critical = int(hotspot.get("critical", 0) or 0)
        warning = int(hotspot.get("warning", 0) or 0)
        if critical <= 0 and warning <= 0:
            continue
        file_scores[path] += min(6, critical * 2 + warning // 3)
        evidence[path].add("hotspot")


def apply_hint_component_hotspot_scores(
    *,
    snapshot: Any,
    signals: Any,
    file_scores: Any,
    evidence: dict[str, set[str]],
    is_relevant_arch_path: Callable[[str], bool],
) -> None:
    apply_hint_scores(
        snapshot=snapshot,
        signals=signals,
        file_scores=file_scores,
        evidence=evidence,
        is_relevant_arch_path=is_relevant_arch_path,
    )
    apply_component_token_scores(
        snapshot=snapshot,
        signals=signals,
        file_scores=file_scores,
        evidence=evidence,
        is_relevant_arch_path=is_relevant_arch_path,
    )
    apply_hotspot_scores(
        snapshot=snapshot,
        file_scores=file_scores,
        evidence=evidence,
    )
