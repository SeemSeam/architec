from __future__ import annotations

from typing import Any

from .scoring_policy_common import grade_for_score, recommend, to_float, to_int


def evaluate_overall_score(
    *,
    full_score: dict[str, Any],
    incremental_score: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    overall_cfg = (
        policy.get("overall", {})
        if isinstance(policy.get("overall"), dict)
        else {}
    )
    inc_signals = (
        incremental_score.get("signals", {})
        if isinstance(incremental_score.get("signals", {}), dict)
        else {}
    )
    weights = overall_cfg.get("weights", {}) if isinstance(overall_cfg.get("weights"), dict) else {}
    w_full = to_float(weights.get("full"), 0.55)
    w_inc = to_float(weights.get("incremental"), 0.45)
    low_scope_reason = ""

    inc_mode = str(incremental_score.get("mode", "") or "")
    if inc_mode in {"no_change", "not_applicable"}:
        w_full, w_inc = 1.0, 0.0
    else:
        w_full, w_inc, low_scope_reason = _apply_low_scope_reweight(
            overall_cfg=overall_cfg,
            inc_signals=inc_signals,
            w_full=w_full,
            w_inc=w_inc,
        )

    w_full, w_inc = _normalize_weights(w_full, w_inc)
    score = (
        to_float(full_score.get("score"), 0.0) * w_full
        + to_float(incremental_score.get("score"), 0.0) * w_inc
    )
    pass_min = to_float(overall_cfg.get("pass_min"), 75.0)
    warn_min = to_float(overall_cfg.get("warn_min"), 60.0)
    recommendation = recommend(score, pass_min=pass_min, warn_min=warn_min)

    reasons = [f"overall score composed from full({w_full:.2f}) + incremental({w_inc:.2f})."]
    if inc_mode == "not_applicable":
        reasons.append("incremental score not applicable in full analysis; overall follows full score.")
    if low_scope_reason:
        reasons.append(low_scope_reason)
    recommendation, escalation_reason = _apply_escalation_rules(
        overall_cfg=overall_cfg,
        full_score=full_score,
        incremental_score=incremental_score,
        inc_signals=inc_signals,
        recommendation=recommendation,
    )
    if escalation_reason:
        reasons.extend(escalation_reason)

    return {
        "mode": "overall",
        "score": round(score, 2),
        "grade": grade_for_score(score, policy),
        "recommendation": recommendation,
        "gate_passed": recommendation != "block",
        "ship_ready": recommendation == "approve",
        "thresholds": {"pass_min": pass_min, "warn_min": warn_min},
        "weights": {"full": round(w_full, 3), "incremental": round(w_inc, 3)},
        "reasons": reasons,
    }


def _normalize_weights(w_full: float, w_inc: float) -> tuple[float, float]:
    if w_full < 0:
        w_full = 0.0
    if w_inc < 0:
        w_inc = 0.0
    if w_full + w_inc <= 0:
        return 1.0, 0.0
    norm = w_full + w_inc
    return w_full / norm, w_inc / norm


def _apply_low_scope_reweight(
    *,
    overall_cfg: dict[str, Any],
    inc_signals: dict[str, Any],
    w_full: float,
    w_inc: float,
) -> tuple[float, float, str]:
    low_scope_cfg = (
        overall_cfg.get("low_scope_reweight", {})
        if isinstance(overall_cfg.get("low_scope_reweight"), dict)
        else {}
    )
    if not bool(low_scope_cfg.get("enabled", True)):
        return w_full, w_inc, ""
    changed_file_total = to_int(inc_signals.get("changed_file_total"), -1)
    component_total = to_int(inc_signals.get("component_total"), -1)
    max_changed = to_int(low_scope_cfg.get("max_changed_files"), 3)
    max_components = to_int(low_scope_cfg.get("max_components"), 1)
    low_scope_weight = to_float(low_scope_cfg.get("incremental_weight"), 0.12)
    changed_ok = changed_file_total >= 0 and changed_file_total <= max_changed
    components_ok = component_total >= 0 and component_total <= max_components
    if not (changed_ok and components_ok and low_scope_weight < w_inc):
        return w_full, w_inc, ""
    w_inc = min(max(low_scope_weight, 0.0), 1.0)
    w_full = max(0.0, 1.0 - w_inc)
    reason = (
        "low-scope incremental reweight applied "
        f"(changed_files={changed_file_total}, components={component_total}, "
        f"incremental_weight={w_inc:.2f})."
    )
    return w_full, w_inc, reason


def _apply_escalation_rules(
    *,
    overall_cfg: dict[str, Any],
    full_score: dict[str, Any],
    incremental_score: dict[str, Any],
    inc_signals: dict[str, Any],
    recommendation: str,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if bool(overall_cfg.get("escalate_when_incremental_blocked", True)) and str(
        incremental_score.get("recommendation", "")
    ) == "block":
        blocked_components = to_int(inc_signals.get("blocked_components"), 0)
        critical_total = to_int(inc_signals.get("critical_total"), 0)
        blocked_min = to_int(overall_cfg.get("incremental_block_escalation_min_blocked_components"), 1)
        critical_min = to_int(overall_cfg.get("incremental_block_escalation_min_critical_total"), 1)
        if blocked_components >= blocked_min or critical_total >= critical_min:
            recommendation = "block"
            reasons.append("incremental gate blocked; escalated to overall block "
                           f"(blocked_components={blocked_components}, critical_total={critical_total}).")
    if bool(overall_cfg.get("escalate_when_full_blocked", False)) and str(
        full_score.get("recommendation", "")
    ) == "block":
        recommendation = "block"
        reasons.append("full governance blocked; escalated to overall block.")
    return recommendation, reasons
