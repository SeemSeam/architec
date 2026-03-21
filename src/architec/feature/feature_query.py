from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .feature_query_scoring import (
    aggregate_component_scores,
    build_hint_scores,
    build_token_weights,
)


_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_./-]{1,}")
_COMPONENT_TOKEN_RE = re.compile(r"[a-z0-9_]{3,}")

_STOPWORDS = {
    "the",
    "a",
    "an",
    "for",
    "and",
    "or",
    "to",
    "of",
    "in",
    "on",
    "with",
    "by",
    "is",
    "are",
    "be",
    "as",
    "this",
    "that",
    "it",
    "from",
    "at",
    "into",
    "new",
    "feature",
    "please",
    "add",
    "implement",
    "support",
    "current",
    "project",
    "review",
    "analyze",
    "analysis",
    "improve",
    "improvement",
    "architecture",
    "system",
    "stability",
    "stable",
    "优化",
    "实现",
    "功能",
    "建议",
    "需要",
    "新增",
    "问题",
    "如何",
    "一个",
    "进行",
    "当前",
    "项目",
    "代码",
    "分析",
    "架构",
    "稳定",
}

@dataclass(frozen=True)
class GoalSignals:
    goal_text: str
    goal_low: str
    tokens: list[str]
    weighted_tokens: dict[str, float]
    hint_scores: dict[str, float]


def extract_goal_tokens(text: str) -> list[str]:
    tokens = [m.group(0).lower() for m in _TOKEN_RE.finditer(text or "")]
    clean = [t for t in tokens if len(t) >= 3 and t not in _STOPWORDS]
    return clean[:80]


def component_tokens(component: str) -> list[str]:
    text = str(component or "").lower().replace(":", "/").replace("-", "_")
    out: list[str] = []
    for token in _COMPONENT_TOKEN_RE.findall(text):
        if token in _STOPWORDS:
            continue
        out.append(token)
    return out[:8]


def build_goal_signals(
    goal: str,
    *,
    searchable_documents: list[str],
) -> GoalSignals:
    goal_low = str(goal or "").lower()
    tokens = extract_goal_tokens(goal)
    weighted_tokens = build_token_weights(
        tokens,
        searchable_documents=searchable_documents,
        doc_token_set=_doc_token_set,
    )
    hint_scores = build_hint_scores(goal_low)
    return GoalSignals(
        goal_text=str(goal or ""),
        goal_low=goal_low,
        tokens=tokens,
        weighted_tokens=weighted_tokens,
        hint_scores=hint_scores,
    )


def _doc_token_set(text: str) -> set[str]:
    raw = str(text or "").lower().replace("/", " ").replace("-", " ").replace(".", " ")
    return {m.group(0).lower() for m in _TOKEN_RE.finditer(raw)}
def aggregate_component_candidate_scores(
    candidate_files: list[dict[str, Any]],
) -> tuple[dict[str, float], dict[str, list[str]]]:
    return aggregate_component_scores(candidate_files)
