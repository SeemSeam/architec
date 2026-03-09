"""Architec analysis engine.

Independent from runtime proxy internals; integrates with Hippocampus via
read-only `.hippocampus` artifacts and writes its own outputs to `.architec`.
"""

from .analysis_runner import run_analysis
from .feature_advisor import suggest_feature_architecture
from .history_analyzer import analyze_history_and_iterate
from .component_scoring import score_changed_components
from .scoring_policy import (
    evaluate_full_score,
    evaluate_incremental_score,
    evaluate_overall_score,
    load_scoring_policy,
)

__all__ = [
    'run_analysis',
    'analyze_history_and_iterate',
    'suggest_feature_architecture',
    'score_changed_components',
    'load_scoring_policy',
    'evaluate_full_score',
    'evaluate_incremental_score',
    'evaluate_overall_score',
]
