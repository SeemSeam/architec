"""Architec analysis engine.

Independent from runtime proxy internals; integrates with Hippos via
read-only `.hippos` artifacts and writes its own outputs to `.architec`.
"""

__all__ = [
    "run_analysis",
    "analyze_history_and_iterate",
    "suggest_feature_architecture",
    "score_changed_components",
    "load_scoring_policy",
    "evaluate_full_score",
    "evaluate_incremental_score",
    "evaluate_overall_score",
]


def __getattr__(name: str):
    if name == "run_analysis":
        from .analysis.public import run_analysis

        return run_analysis
    if name == "analyze_history_and_iterate":
        from .analysis.history_analyzer import analyze_history_and_iterate

        return analyze_history_and_iterate
    if name == "suggest_feature_architecture":
        from .feature.feature_advisor import suggest_feature_architecture

        return suggest_feature_architecture
    if name == "score_changed_components":
        from .scoring.component_scoring import score_changed_components

        return score_changed_components
    if name == "load_scoring_policy":
        from .scoring.public import load_scoring_policy

        return load_scoring_policy
    if name == "evaluate_full_score":
        from .scoring.public import evaluate_full_score

        return evaluate_full_score
    if name == "evaluate_incremental_score":
        from .scoring.public import evaluate_incremental_score

        return evaluate_incremental_score
    if name == "evaluate_overall_score":
        from .scoring.public import evaluate_overall_score

        return evaluate_overall_score
    raise AttributeError(f"module 'architec' has no attribute {name!r}")
