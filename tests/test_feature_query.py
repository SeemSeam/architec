from __future__ import annotations

from architec.feature_query import (
    aggregate_component_candidate_scores,
    build_goal_signals,
    extract_goal_tokens,
)


def test_extract_goal_tokens_filters_stopwords() -> None:
    tokens = extract_goal_tokens("please improve current project stability for context continuity")
    assert "please" not in tokens
    assert "current" not in tokens
    assert "continuity" in tokens


def test_build_goal_signals_applies_hint_scores() -> None:
    signals = build_goal_signals(
        "Improve context continuity and semantic compression",
        searchable_documents=["context continuity semantic compression"],
    )
    assert signals.hint_scores["llm-proxy:ops/context"] > 0


def test_aggregate_component_candidate_scores_weights_top_paths() -> None:
    scores, evidence = aggregate_component_candidate_scores(
        [
            {"component": "a:b", "path": "x.py", "score": 10},
            {"component": "a:b", "path": "y.py", "score": 7},
            {"component": "a:b", "path": "z.py", "score": 5},
            {"component": "c:d", "path": "m.py", "score": 4},
        ]
    )
    assert scores["a:b"] > scores["c:d"]
    assert evidence["a:b"] == ["x.py", "y.py", "z.py"]

