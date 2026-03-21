from __future__ import annotations

from typing import Any

from architec.support.io_utils import clamp
from architec.scoring.scoring_policy_common import to_float, to_int


def component_score(item: dict[str, Any]) -> float:
    return clamp(to_float(item.get("score"), 0.0), 0.0, 100.0)


def component_critical(item: dict[str, Any]) -> int:
    findings = item.get("findings", {}) if isinstance(item.get("findings"), dict) else {}
    return to_int(findings.get("critical"), 0)


def component_weight(item: dict[str, Any], mode: str, *, churn_cap: float = 0.0) -> float:
    if mode not in {"churn", "churn_capped", "sqrt_churn"}:
        return 1.0

    churn = item.get("churn", {}) if isinstance(item.get("churn"), dict) else {}
    total = to_float(churn.get("total"), 0.0)
    if mode == "sqrt_churn":
        weight = max(1.0, total**0.5 + 1.0)
    else:
        weight = max(1.0, total + 1.0)
    if mode == "churn_capped" or churn_cap > 0:
        cap = churn_cap if churn_cap > 0 else 24.0
        weight = min(weight, max(1.0, cap))
    return weight


def collect_incremental_signals(
    components: list[dict[str, Any]],
    *,
    weight_mode: str,
    churn_cap: float,
    score_floor: float,
    critical_limit: int,
    warn_min: float,
) -> dict[str, Any]:
    total_weight = 0.0
    weighted_score = 0.0
    critical_total = 0
    trend_up_components = 0
    blocked_components: list[str] = []
    weak_components: list[str] = []

    for comp in components:
        name = str(comp.get("component", "") or "unknown")
        score = component_score(comp)
        critical = component_critical(comp)
        critical_total += critical
        if str(comp.get("trend", "")).strip().lower() == "up":
            trend_up_components += 1
        weight = component_weight(comp, weight_mode, churn_cap=churn_cap)
        total_weight += weight
        weighted_score += score * weight

        component_blocked = (
            str(comp.get("recommendation", "")) == "block"
            or score < score_floor
            or (critical_limit > 0 and critical >= critical_limit)
        )
        if component_blocked:
            blocked_components.append(name)
            continue
        if score < warn_min:
            weak_components.append(name)

    raw_score = weighted_score / total_weight if total_weight > 0 else 0.0
    return {
        "raw_score": raw_score,
        "critical_total": critical_total,
        "trend_up_components": trend_up_components,
        "blocked_components": blocked_components,
        "weak_components": weak_components,
    }
