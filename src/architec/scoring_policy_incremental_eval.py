from __future__ import annotations

from typing import Any

from .io_utils import clamp
from .scoring_policy_common import grade_for_score, recommend, to_float, to_int
from .scoring_policy_incremental_helpers import collect_incremental_signals
from .scoring_policy_incremental_reasoning import (
    incremental_reasons,
    macro_bonus,
    no_change_result,
)


def evaluate_incremental_score(
    *,
    components: list[dict[str, Any]],
    changed_file_total: int,
    policy: dict[str, Any],
) -> dict[str, Any]:
    inc_cfg = (
        policy.get("incremental", {})
        if isinstance(policy.get("incremental"), dict)
        else {}
    )
    if changed_file_total <= 0 and not components:
        return no_change_result(policy=policy, inc_cfg=inc_cfg)

    weight_mode = str(inc_cfg.get("weight_by", "churn_capped") or "churn_capped")
    churn_cap = to_float(inc_cfg.get("churn_weight_cap"), 0.0)
    score_floor = to_float(inc_cfg.get("score_floor_per_component"), 40.0)
    critical_limit = to_int(inc_cfg.get("critical_per_component_hard_limit"), 3)
    critical_total_hard_limit = to_int(inc_cfg.get("critical_total_hard_limit"), 0)
    blocked_limit = to_int(inc_cfg.get("blocked_component_limit"), 0)
    warn_min = to_float(inc_cfg.get("warn_min"), 60.0)
    signals = collect_incremental_signals(
        components,
        weight_mode=weight_mode,
        churn_cap=churn_cap,
        score_floor=score_floor,
        critical_limit=critical_limit,
        warn_min=warn_min,
    )

    crit_pen_cfg = (
        inc_cfg.get("critical_penalty", {})
        if isinstance(inc_cfg.get("critical_penalty"), dict)
        else {}
    )
    critical_penalty = min(
        to_float(crit_pen_cfg.get("max_total"), 12.0),
        signals["critical_total"] * to_float(crit_pen_cfg.get("per_critical"), 2.0),
    )
    macro_bonus_value = macro_bonus(
        inc_cfg=inc_cfg,
        trend_up_components=signals["trend_up_components"],
    )
    score = clamp(signals["raw_score"] - critical_penalty + macro_bonus_value, 0.0, 100.0)

    pass_min = to_float(inc_cfg.get("pass_min"), 80.0)
    recommendation = recommend(score, pass_min=pass_min, warn_min=warn_min)
    reasons = incremental_reasons(
        recommendation=recommendation,
        blocked_components=signals["blocked_components"],
        weak_components=signals["weak_components"],
        critical_total=signals["critical_total"],
        critical_total_hard_limit=critical_total_hard_limit,
        blocked_limit=blocked_limit,
        macro_bonus_value=macro_bonus_value,
        trend_up_components=signals["trend_up_components"],
    )
    if reasons["force_block"]:
        recommendation = "block"

    return {
        "mode": "incremental",
        "score": round(score, 2),
        "grade": grade_for_score(score, policy),
        "recommendation": recommendation,
        "gate_passed": recommendation != "block",
        "ship_ready": recommendation == "approve",
        "signals": {
            "changed_file_total": to_int(changed_file_total, 0),
            "component_total": len(components),
            "blocked_components": len(signals["blocked_components"]),
            "blocked_component_names": signals["blocked_components"][:20],
            "critical_total": signals["critical_total"],
            "raw_weighted_score": round(signals["raw_score"], 2),
            "critical_penalty": round(critical_penalty, 2),
            "trend_up_components": signals["trend_up_components"],
            "macro_progress_bonus": round(macro_bonus_value, 2),
        },
        "thresholds": {
            "pass_min": pass_min,
            "warn_min": warn_min,
            "churn_weight_cap": churn_cap,
            "score_floor_per_component": score_floor,
            "critical_per_component_hard_limit": critical_limit,
            "critical_total_hard_limit": critical_total_hard_limit,
            "blocked_component_limit": blocked_limit,
        },
        "reasons": reasons["items"],
    }
