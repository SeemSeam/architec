from __future__ import annotations

from typing import Any

from .io_utils import clamp
from .scoring_policy_common import grade_for_score, recommend, to_float, to_int


def evaluate_full_score(
    *,
    summary: dict[str, Any],
    baseline_scores: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    full_cfg = policy.get("full", {}) if isinstance(policy.get("full"), dict) else {}
    base_cfg = (
        full_cfg.get("base_score", {})
        if isinstance(full_cfg.get("base_score"), dict)
        else {}
    )
    pen_cfg = (
        full_cfg.get("severity_penalty", {})
        if isinstance(full_cfg.get("severity_penalty"), dict)
        else {}
    )
    by_sev = summary.get("by_severity", {}) if isinstance(summary.get("by_severity"), dict) else {}
    critical = to_int(by_sev.get("critical"), 0)
    warning = to_int(by_sev.get("warning"), 0)
    info = to_int(by_sev.get("info"), 0)

    base_mode = str(base_cfg.get("mode", "fixed_100") or "fixed_100").strip().lower()
    if base_mode in {"fixed_100", "fixed"}:
        base_score = clamp(to_float(base_cfg.get("fixed"), 100.0), 0.0, 100.0)
        base_source = "policy.full.base_score.fixed"
    elif base_mode in {"baseline_overall_x10", "baseline"}:
        raw = baseline_scores.get("overall", None)
        if raw is None:
            base_score = 100.0
            base_source = "default"
        else:
            base_score = clamp(to_float(raw, 10.0) * 10.0, 0.0, 100.0)
            base_source = "baseline_scores.overall"
    else:
        base_score = 100.0
        base_source = f"fallback:{base_mode}"

    p_critical = min(
        to_float(pen_cfg.get("max_critical"), 30.0),
        critical * to_float(pen_cfg.get("per_critical"), 0.06),
    )
    p_warning = min(
        to_float(pen_cfg.get("max_warning"), 18.0),
        warning * to_float(pen_cfg.get("per_warning"), 0.02),
    )
    p_info = min(to_float(pen_cfg.get("max_info"), 8.0), info * to_float(pen_cfg.get("per_info"), 0.005))
    penalty_total = p_critical + p_warning + p_info
    score = clamp(base_score - penalty_total, 0.0, 100.0)

    pass_min_cfg = to_float(full_cfg.get("pass_min"), 75.0)
    warn_min_cfg = to_float(full_cfg.get("warn_min"), 60.0)
    pass_min, warn_min = pass_min_cfg, warn_min_cfg
    adaptive_cfg = (
        full_cfg.get("adaptive_thresholds", {})
        if isinstance(full_cfg.get("adaptive_thresholds"), dict)
        else {}
    )
    if bool(adaptive_cfg.get("enabled", False)):
        pass_relief = min(
            to_float(adaptive_cfg.get("max_pass_relief"), 20.0),
            penalty_total * to_float(adaptive_cfg.get("pass_relief_per_penalty"), 0.35),
        )
        warn_relief = min(
            to_float(adaptive_cfg.get("max_warn_relief"), 15.0),
            penalty_total * to_float(adaptive_cfg.get("warn_relief_per_penalty"), 0.25),
        )
        pass_min = max(to_float(adaptive_cfg.get("pass_floor"), 65.0), pass_min_cfg - pass_relief)
        warn_min = max(to_float(adaptive_cfg.get("warn_floor"), 50.0), warn_min_cfg - warn_relief)
        warn_min = min(warn_min, pass_min - to_float(adaptive_cfg.get("min_pass_warn_gap"), 5.0))
        warn_min = max(0.0, warn_min)

    recommendation = recommend(score, pass_min=pass_min, warn_min=warn_min)
    hard_limit = to_int(full_cfg.get("critical_hard_limit"), 0)
    reasons: list[str] = []
    if hard_limit > 0 and critical >= hard_limit:
        recommendation = "block"
        reasons.append(f"critical findings {critical} exceed hard limit {hard_limit} in full baseline.")
    if not reasons:
        reasons.append(f"severity pressure applied (critical={critical}, warning={warning}, info={info}).")

    return {
        "mode": "full",
        "score": round(score, 2),
        "grade": grade_for_score(score, policy),
        "recommendation": recommendation,
        "gate_passed": recommendation != "block",
        "ship_ready": recommendation == "approve",
        "signals": {
            "critical": critical,
            "warning": warning,
            "info": info,
            "base_score": round(base_score, 2),
            "base_score_source": base_source,
            "penalty": {
                "critical": round(p_critical, 2),
                "warning": round(p_warning, 2),
                "info": round(p_info, 2),
                "total": round(penalty_total, 2),
            },
        },
        "thresholds": {
            "configured_pass_min": pass_min_cfg,
            "configured_warn_min": warn_min_cfg,
            "pass_min": pass_min,
            "warn_min": warn_min,
            "critical_hard_limit": hard_limit,
        },
        "reasons": reasons,
    }
