from __future__ import annotations

from typing import Any

from .scoring_policy_common import grade_for_score, to_float, to_int


def macro_bonus(*, inc_cfg: dict[str, Any], trend_up_components: int) -> float:
    macro_cfg = (
        inc_cfg.get("macro_progress_bonus", {})
        if isinstance(inc_cfg.get("macro_progress_bonus"), dict)
        else {}
    )
    if not bool(macro_cfg.get("enabled", True)):
        return 0.0
    return min(
        to_float(macro_cfg.get("max_total"), 0.0),
        trend_up_components * to_float(macro_cfg.get("trend_up_per_component"), 0.0),
    )


def no_change_result(*, policy: dict[str, Any], inc_cfg: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": "no_change",
        "score": 100.0,
        "grade": grade_for_score(100.0, policy),
        "recommendation": "approve",
        "gate_passed": True,
        "ship_ready": True,
        "signals": {
            "changed_file_total": 0,
            "component_total": 0,
            "blocked_components": 0,
            "critical_total": 0,
        },
        "thresholds": {
            "pass_min": to_float(inc_cfg.get("pass_min"), 80.0),
            "warn_min": to_float(inc_cfg.get("warn_min"), 60.0),
            "blocked_component_limit": to_int(inc_cfg.get("blocked_component_limit"), 0),
        },
        "reasons": ["no changed files detected; incremental gate is green."],
    }


def incremental_reasons(
    *,
    recommendation: str,
    blocked_components: list[str],
    weak_components: list[str],
    critical_total: int,
    critical_total_hard_limit: int,
    blocked_limit: int,
    macro_bonus_value: float,
    trend_up_components: int,
) -> dict[str, Any]:
    items: list[str] = []
    force_block = recommendation == "block"
    if critical_total_hard_limit > 0 and critical_total >= critical_total_hard_limit:
        force_block = True
        items.append(f"critical total {critical_total} exceeds hard limit {critical_total_hard_limit}.")
    if len(blocked_components) > blocked_limit:
        force_block = True
        items.append(f"blocked component count {len(blocked_components)} exceeds limit {blocked_limit}.")
    if macro_bonus_value > 0:
        items.append(
            f"macro progress bonus +{macro_bonus_value:.2f} "
            f"from {trend_up_components} improving components."
        )
    if not items and weak_components:
        items.append(f"weak components detected: {', '.join(weak_components[:6])}.")
    if not items:
        items.append("incremental gate derived from changed component scores and churn.")
    return {"items": items, "force_block": force_block}
