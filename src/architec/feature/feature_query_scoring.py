from __future__ import annotations

import math
from typing import Any


WEAK_HINT_TERMS = {
    "llm-proxy:gateway": ["gateway", "provider", "model", "网关", "模型"],
    "llm-proxy:ops/context": ["context", "topic", "nav", "上下文", "话题", "导航"],
    "llm-proxy:project_router": ["session", "isolation", "会话", "隔离"],
    "hippos:nav": ["navigate", "focus", "snippet", "焦点", "片段"],
    "hippos:tools": ["index", "map", "structure", "indexing", "索引", "地图", "结构"],
    "hippos:memory": ["memory", "summary", "store", "记忆", "摘要", "存储"],
    "hippos:mcp": ["mcp", "tool", "tools", "server", "工具", "服务"],
}

STRONG_HINT_TERMS = {
    "llm-proxy:gateway": ["gateway/server", "gateway/config", "gateway server"],
    "llm-proxy:ops/context": [
        "compaction",
        "context continuity",
        "context continuity",
        "navigation focus",
        "topic bank",
        "semantic compression",
        "压缩",
        "连续性",
    ],
    "llm-proxy:project_router": ["project_router", "route isolation"],
    "hippos:nav": ["repomap", "navigate.py"],
    "hippos:tools": ["architect tool", "reviewer tool"],
}


def _hint_hits(goal_low: str, terms: list[str]) -> int:
    return sum(1 for term in terms if term and term.lower() in goal_low)


def _strong_hint_bonus(goal_low: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for component, terms in STRONG_HINT_TERMS.items():
        hits = _hint_hits(goal_low, terms)
        if hits > 0:
            out[component] = 7.0 * hits
    return out


def _weak_hint_bonus(goal_low: str, strong_scores: dict[str, float]) -> dict[str, float]:
    out: dict[str, float] = {}
    for component, terms in WEAK_HINT_TERMS.items():
        hits = _hint_hits(goal_low, terms)
        if hits >= 2:
            out[component] = 4.0 + float(hits - 2)
        elif hits == 1 and component in STRONG_HINT_TERMS and strong_scores.get(component, 0.0) > 0:
            out[component] = 2.0
    return out


def build_token_weights(
    tokens: list[str],
    *,
    searchable_documents: list[str],
    doc_token_set,
) -> dict[str, float]:
    docs = [doc_token_set(doc) for doc in searchable_documents if str(doc or "").strip()]
    total_docs = max(1, len(docs))
    out: dict[str, float] = {}
    for token in tokens:
        match_docs = sum(1 for doc in docs if token in doc)
        coverage = match_docs / total_docs
        if coverage >= 0.6:
            continue
        if coverage <= 0.05:
            out[token] = 1.0
            continue
        out[token] = max(0.2, min(1.0, math.log((total_docs + 1.0) / (match_docs + 1.0))))
    return out


def build_hint_scores(goal_low: str) -> dict[str, float]:
    out = _strong_hint_bonus(goal_low)
    for component, bonus in _weak_hint_bonus(goal_low, out).items():
        out[component] = out.get(component, 0.0) + bonus
    return out


def _collect_component_scores(
    candidate_files: list[dict[str, Any]],
) -> tuple[dict[str, list[int]], dict[str, list[str]]]:
    grouped_scores: dict[str, list[int]] = {}
    grouped_paths: dict[str, list[str]] = {}
    for item in candidate_files:
        component = str(item.get("component", "") or "")
        score = int(item.get("score", 0) or 0)
        if not component or score <= 0:
            continue
        grouped_scores.setdefault(component, []).append(score)
        path = str(item.get("path", "") or "")
        if path and path not in grouped_paths.setdefault(component, []):
            grouped_paths[component].append(path)
    return grouped_scores, grouped_paths


def _weighted_component_score(scores: list[int], path_count: int) -> float:
    weighted = 0.0
    for idx, score in enumerate(sorted(scores, reverse=True)[:3]):
        weight = 1.0 if idx == 0 else 0.65 if idx == 1 else 0.35
        weighted += score * weight
    diversity_bonus = min(3.0, max(0.0, float(path_count - 1)))
    return round(weighted + diversity_bonus, 2)


def aggregate_component_scores(
    candidate_files: list[dict[str, Any]],
) -> tuple[dict[str, float], dict[str, list[str]]]:
    grouped_scores, grouped_paths = _collect_component_scores(candidate_files)
    aggregated: dict[str, float] = {}
    for component, scores in grouped_scores.items():
        aggregated[component] = _weighted_component_score(scores, len(grouped_paths.get(component, ())))
    return aggregated, grouped_paths
