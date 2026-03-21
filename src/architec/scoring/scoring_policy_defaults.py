from __future__ import annotations

from typing import Any


DEFAULT_POLICY: dict[str, Any] = {
    "version": "1.0",
    "grade_bands": [
        {"grade": "A", "min": 85},
        {"grade": "B", "min": 70},
        {"grade": "C", "min": 55},
        {"grade": "D", "min": 40},
        {"grade": "E", "min": 0},
    ],
    "full": {
        "pass_min": 75.0,
        "warn_min": 60.0,
        "critical_hard_limit": 400,
        "base_score": {
            "mode": "fixed_100",
            "fixed": 100.0,
        },
        "adaptive_thresholds": {
            "enabled": True,
            "pass_relief_per_penalty": 0.35,
            "warn_relief_per_penalty": 0.25,
            "max_pass_relief": 20.0,
            "max_warn_relief": 15.0,
            "pass_floor": 65.0,
            "warn_floor": 50.0,
            "min_pass_warn_gap": 5.0,
        },
        "severity_penalty": {
            "grace_critical": 5,
            "grace_warning": 20,
            "grace_info": 25,
            "per_critical": 0.5,
            "per_warning": 0.06,
            "per_info": 0.005,
            "max_critical": 45.0,
            "max_warning": 18.0,
            "max_info": 6.0,
        },
    },
    "incremental": {
        "pass_min": 80.0,
        "warn_min": 60.0,
        "weight_by": "churn_capped",
        "churn_weight_cap": 24.0,
        "score_floor_per_component": 40.0,
        "critical_per_component_hard_limit": 3,
        "critical_total_hard_limit": 6,
        "blocked_component_limit": 2,
        "critical_penalty": {"per_critical": 2.0, "max_total": 12.0},
        "macro_progress_bonus": {
            "enabled": True,
            "trend_up_per_component": 1.5,
            "max_total": 7.0,
        },
    },
    "overall": {
        "weights": {"full": 0.62, "incremental": 0.38},
        "low_scope_reweight": {
            "enabled": True,
            "max_changed_files": 3,
            "max_components": 1,
            "incremental_weight": 0.12,
        },
        "pass_min": 75.0,
        "warn_min": 60.0,
        "escalate_when_incremental_blocked": True,
        "incremental_block_escalation_min_blocked_components": 2,
        "incremental_block_escalation_min_critical_total": 3,
        "escalate_when_full_blocked": False,
    },
}
