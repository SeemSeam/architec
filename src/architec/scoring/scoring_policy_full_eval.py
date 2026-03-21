from __future__ import annotations

from typing import Any

from architec.support.io_utils import clamp
from architec.scoring.scoring_policy_common import grade_for_score, recommend, to_float, to_int


def _full_cfg_sections(
    policy: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
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
    return full_cfg, base_cfg, pen_cfg


def _severity_counts(summary: dict[str, Any]) -> tuple[int, int, int]:
    by_sev = (
        summary.get("by_severity", {})
        if isinstance(summary.get("by_severity"), dict)
        else {}
    )
    return (
        to_int(by_sev.get("critical"), 0),
        to_int(by_sev.get("warning"), 0),
        to_int(by_sev.get("info"), 0),
    )


def _resolve_base_score(
    *,
    base_cfg: dict[str, Any],
    baseline_scores: dict[str, Any],
) -> tuple[float, str]:
    base_mode = str(base_cfg.get("mode", "fixed_100") or "fixed_100").strip().lower()
    if base_mode in {"fixed_100", "fixed"}:
        return clamp(to_float(base_cfg.get("fixed"), 100.0), 0.0, 100.0), (
            "policy.full.base_score.fixed"
        )
    if base_mode in {"baseline_overall_x10", "baseline"}:
        raw = baseline_scores.get("overall", None)
        if raw is None:
            return 100.0, "default"
        return clamp(to_float(raw, 10.0) * 10.0, 0.0, 100.0), (
            "baseline_scores.overall"
        )
    return 100.0, f"fallback:{base_mode}"


def _severity_penalties(
    *,
    pen_cfg: dict[str, Any],
    critical: int,
    warning: int,
    info: int,
) -> tuple[float, float, float, float]:
    critical = max(0, critical - to_int(pen_cfg.get("grace_critical"), 0))
    warning = max(0, warning - to_int(pen_cfg.get("grace_warning"), 0))
    info = max(0, info - to_int(pen_cfg.get("grace_info"), 0))
    p_critical = min(
        to_float(pen_cfg.get("max_critical"), 30.0),
        critical * to_float(pen_cfg.get("per_critical"), 0.06),
    )
    p_warning = min(
        to_float(pen_cfg.get("max_warning"), 18.0),
        warning * to_float(pen_cfg.get("per_warning"), 0.02),
    )
    p_info = min(
        to_float(pen_cfg.get("max_info"), 8.0),
        info * to_float(pen_cfg.get("per_info"), 0.005),
    )
    return p_critical, p_warning, p_info, p_critical + p_warning + p_info


def _adaptive_thresholds(
    *,
    full_cfg: dict[str, Any],
    penalty_total: float,
) -> tuple[float, float, float, float]:
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
            penalty_total
            * to_float(adaptive_cfg.get("pass_relief_per_penalty"), 0.35),
        )
        warn_relief = min(
            to_float(adaptive_cfg.get("max_warn_relief"), 15.0),
            penalty_total
            * to_float(adaptive_cfg.get("warn_relief_per_penalty"), 0.25),
        )
        pass_min = max(
            to_float(adaptive_cfg.get("pass_floor"), 65.0),
            pass_min_cfg - pass_relief,
        )
        warn_min = max(
            to_float(adaptive_cfg.get("warn_floor"), 50.0),
            warn_min_cfg - warn_relief,
        )
        warn_min = min(
            warn_min,
            pass_min - to_float(adaptive_cfg.get("min_pass_warn_gap"), 5.0),
        )
        warn_min = max(0.0, warn_min)
    return pass_min_cfg, warn_min_cfg, pass_min, warn_min


def _resolve_recommendation(
    *,
    score: float,
    full_cfg: dict[str, Any],
    pass_min: float,
    warn_min: float,
    critical: int,
) -> tuple[str, int, list[str]]:
    recommendation = recommend(score, pass_min=pass_min, warn_min=warn_min)
    hard_limit = to_int(full_cfg.get("critical_hard_limit"), 0)
    reasons: list[str] = []
    if hard_limit > 0 and critical >= hard_limit:
        recommendation = "block"
        reasons.append(
            f"critical findings {critical} exceed hard limit {hard_limit} "
            "in full baseline."
        )
    return recommendation, hard_limit, reasons


def evaluate_full_score(
    *,
    summary: dict[str, Any],
    baseline_scores: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    full_cfg, base_cfg, pen_cfg = _full_cfg_sections(policy)
    critical, warning, info = _severity_counts(summary)
    base_score, base_source = _resolve_base_score(
        base_cfg=base_cfg,
        baseline_scores=baseline_scores,
    )
    p_critical, p_warning, p_info, penalty_total = _severity_penalties(
        pen_cfg=pen_cfg,
        critical=critical,
        warning=warning,
        info=info,
    )
    score = clamp(base_score - penalty_total, 0.0, 100.0)
    pass_min_cfg, warn_min_cfg, pass_min, warn_min = _adaptive_thresholds(
        full_cfg=full_cfg,
        penalty_total=penalty_total,
    )
    recommendation, hard_limit, reasons = _resolve_recommendation(
        score=score,
        full_cfg=full_cfg,
        pass_min=pass_min,
        warn_min=warn_min,
        critical=critical,
    )
    if not reasons:
        reasons.append(
            "severity pressure applied "
            f"(critical={critical}, warning={warning}, info={info})."
        )

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
