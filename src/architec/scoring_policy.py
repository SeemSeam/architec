from __future__ import annotations

from typing import Any

from .scoring_policy_common import load_scoring_policy
from .scoring_policy_defaults import DEFAULT_POLICY
from .scoring_policy_full_eval import evaluate_full_score
from .scoring_policy_incremental_eval import evaluate_incremental_score
from .scoring_policy_overall_eval import evaluate_overall_score


__all__ = [
    "DEFAULT_POLICY",
    "load_scoring_policy",
    "evaluate_full_score",
    "evaluate_incremental_score",
    "evaluate_overall_score",
]


def as_scoring_snapshot(
    *,
    full_score: dict[str, Any],
    incremental_score: dict[str, Any],
    overall_score: dict[str, Any],
) -> dict[str, Any]:
    full_value = float(full_score.get("score", 0.0) or 0.0)
    incremental_mode = str(incremental_score.get("mode", "") or "")
    incremental_value = (
        float(incremental_score.get("score", 0.0) or 0.0)
        if incremental_mode not in {"", "not_applicable"}
        else None
    )
    values = [full_value]
    if incremental_value is not None:
        values.append(incremental_value)
    total_average = round(sum(values) / max(1, len(values)), 2)
    return {
        "scores": {
            "total_average": total_average,
            "full": float(full_score.get("score", 0.0) or 0.0),
            "incremental": incremental_value,
            "overall": float(overall_score.get("score", 0.0) or 0.0),
        },
        "recommendations": {
            "full": str(full_score.get("recommendation", "") or ""),
            "incremental": str(incremental_score.get("recommendation", "") or ""),
            "overall": str(overall_score.get("recommendation", "") or ""),
        },
    }
