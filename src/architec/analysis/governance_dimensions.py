from __future__ import annotations

from typing import Any

from architec.support.io_utils import clamp

_HOTSPOT_WEIGHTS = (1.0, 0.72, 0.54, 0.4, 0.3, 0.22, 0.16, 0.12)
_COMPONENT_WEIGHTS = (1.0, 0.74, 0.56, 0.42, 0.3, 0.2)
_CLEANUP_CATEGORY_WEIGHTS = {
    "fallback_branch": 4.5,
    "legacy_impl": 4.0,
    "compat_layer": 3.0,
    "obsolete_script": 1.8,
    "stale_config": 1.6,
    "stale_doc": 1.2,
    "stale_prompt": 1.0,
}


def _weighted_average(weighted_values: list[tuple[float, float]]) -> float:
    if not weighted_values:
        return 0.0
    total_weight = sum(weight for _, weight in weighted_values)
    if total_weight <= 0:
        return 0.0
    return sum(value * weight for value, weight in weighted_values) / total_weight


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 1.0
    return min(1.0, max(0.0, float(numerator) / float(denominator)))


def _hotspot_pressure(item: dict[str, Any]) -> float:
    critical = int(item.get("critical", 0) or 0)
    warning = int(item.get("warning", 0) or 0)
    hotspot_score = float(item.get("hotspot_score", item.get("score", 0.0)) or 0.0)
    component_score = item.get("component_score")
    component_penalty = 0.0
    if isinstance(component_score, (int, float)):
        component_penalty = max(0.0, (68.0 - float(component_score)) * 0.22)
    return min(20.0, critical * 5.5 + warning * 1.35 + hotspot_score * 0.75 + component_penalty)


def hotspot_hygiene_score(hotspot_digest: dict[str, Any] | None) -> float:
    items = hotspot_digest.get("items", []) if isinstance(hotspot_digest, dict) else []
    weighted: list[tuple[float, float]] = []
    for idx, item in enumerate(items[: len(_HOTSPOT_WEIGHTS)]):
        if not isinstance(item, dict):
            continue
        weighted.append((_hotspot_pressure(item), _HOTSPOT_WEIGHTS[idx]))
    if not weighted:
        return 100.0
    avg_pressure = _weighted_average(weighted)
    return round(clamp(100.0 - min(46.0, avg_pressure * 2.2), 0.0, 100.0), 2)


def _component_pressure(item: dict[str, Any]) -> float:
    risk_score = float(item.get("risk_score", 0.0) or 0.0)
    critical = int(item.get("critical", 0) or 0)
    warning = int(item.get("warning", 0) or 0)
    file_count = int(item.get("file_count", 0) or 0)
    return min(
        18.0,
        risk_score * 1.35 + critical * 5.0 + warning * 1.1 + max(0, file_count - 6) * 0.5,
    )


def component_balance_score(components: list[dict[str, Any]] | None) -> float:
    if not isinstance(components, list):
        return 100.0
    weighted: list[tuple[float, float]] = []
    for idx, item in enumerate(components[: len(_COMPONENT_WEIGHTS)]):
        if not isinstance(item, dict):
            continue
        weighted.append((_component_pressure(item), _COMPONENT_WEIGHTS[idx]))
    if not weighted:
        return 100.0
    avg_pressure = _weighted_average(weighted)
    return round(clamp(100.0 - min(42.0, avg_pressure * 2.0), 0.0, 100.0), 2)


def _cleanup_category_pressure(by_category: dict[str, Any]) -> float:
    pressure = 0.0
    for category, count in by_category.items():
        if not isinstance(category, str):
            continue
        pressure += int(count or 0) * _CLEANUP_CATEGORY_WEIGHTS.get(category, 1.6)
    return pressure


def cleanup_hygiene_score(cleanup: dict[str, Any] | None) -> float:
    if not isinstance(cleanup, dict):
        return 100.0
    candidate_total = int(cleanup.get("candidate_total", 0) or 0)
    if candidate_total <= 0:
        return 100.0
    review_required_total = int(cleanup.get("review_required_total", 0) or 0)
    expired_total = int(cleanup.get("expired_total", 0) or 0)
    owner_total = int(cleanup.get("owner_total", 0) or 0)
    ttl_total = int(cleanup.get("ttl_total", 0) or 0)
    expires_total = int(cleanup.get("expires_total", 0) or 0)
    by_category = cleanup.get("by_category", {}) if isinstance(cleanup.get("by_category"), dict) else {}
    metadata_coverage = (
        _ratio(owner_total, candidate_total)
        + _ratio(ttl_total, candidate_total)
        + _ratio(expires_total, candidate_total)
    ) / 3.0

    score = 100.0
    score -= min(22.0, max(0, candidate_total - 1) * 1.8)
    score -= min(20.0, review_required_total * 2.8)
    score -= min(22.0, expired_total * 6.0)
    score -= min(20.0, _cleanup_category_pressure(by_category) * 1.5)
    score += metadata_coverage * 8.0
    return round(clamp(score, 0.0, 100.0), 2)


def archive_readiness_score(archive_candidates: dict[str, Any] | None) -> float:
    if not isinstance(archive_candidates, dict):
        return 100.0
    candidate_total = int(archive_candidates.get("candidate_total", 0) or 0)
    if candidate_total <= 0:
        return 100.0
    ready_total = int(archive_candidates.get("ready_total", 0) or 0)
    review_total = int(archive_candidates.get("review_total", 0) or 0)
    ready_ratio = _ratio(ready_total, candidate_total)

    score = 68.0
    score += ready_ratio * 28.0
    score += min(12.0, ready_total * 2.0)
    score -= min(18.0, review_total * 3.0)
    return round(clamp(score, 0.0, 100.0), 2)


def semantic_alignment_score(semantic_judge: dict[str, Any] | None) -> float:
    if not isinstance(semantic_judge, dict):
        return 100.0
    candidate_pool_total = int(semantic_judge.get("candidate_pool_total", 0) or 0)
    if candidate_pool_total <= 0:
        return 100.0
    status = str(semantic_judge.get("status", "") or "skipped").strip().lower()
    if status != "ok":
        return 72.0

    reviewed_total = int(semantic_judge.get("reviewed_total", 0) or 0)
    by_decision = (
        semantic_judge.get("by_decision", {})
        if isinstance(semantic_judge.get("by_decision"), dict)
        else {}
    )
    coverage = _ratio(reviewed_total, candidate_pool_total)
    action_total = int(by_decision.get("retire_now", 0) or 0) + int(
        by_decision.get("archive_first", 0) or 0
    )
    review_total = int(by_decision.get("review", 0) or 0)
    keep_total = int(by_decision.get("keep_active", 0) or 0)
    action_ratio = _ratio(action_total, max(1, reviewed_total))
    review_ratio = _ratio(review_total, max(1, reviewed_total))
    keep_ratio = _ratio(keep_total, max(1, reviewed_total))

    score = 72.0
    score += coverage * 14.0
    score += action_ratio * 12.0
    score -= review_ratio * 8.0
    score -= keep_ratio * 4.0
    return round(clamp(score, 0.0, 100.0), 2)


def governance_dimensions(
    *,
    hotspot_digest: dict[str, Any] | None = None,
    components: list[dict[str, Any]] | None = None,
    cleanup: dict[str, Any] | None = None,
    archive_candidates: dict[str, Any] | None = None,
    semantic_judge: dict[str, Any] | None = None,
) -> dict[str, float]:
    return {
        "hotspot_hygiene": hotspot_hygiene_score(hotspot_digest),
        "component_balance": component_balance_score(components),
        "cleanup_hygiene": cleanup_hygiene_score(cleanup),
        "archive_readiness": archive_readiness_score(archive_candidates),
        "semantic_alignment": semantic_alignment_score(semantic_judge),
    }


__all__ = [
    "archive_readiness_score",
    "cleanup_hygiene_score",
    "component_balance_score",
    "governance_dimensions",
    "hotspot_hygiene_score",
    "semantic_alignment_score",
]
