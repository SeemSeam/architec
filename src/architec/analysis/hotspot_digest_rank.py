from __future__ import annotations

from typing import Any


def dominant_metric(item: dict[str, Any]) -> str:
    top_metrics = item.get("top_metrics", {})
    if isinstance(top_metrics, dict) and top_metrics:
        best = max(top_metrics.items(), key=lambda kv: float(kv[1] or 0.0))[0]
        return str(best or "")
    if int(item.get("critical", 0) or 0) > 0:
        return "cyclomatic_complexity"
    if int(item.get("warning", 0) or 0) > 0:
        return "module_lines"
    return "unknown"


def fix_hint(
    *,
    path: str,
    dominant_metric_name: str,
    is_test_like_path,
    is_doc_like_path,
) -> str:
    metric = str(dominant_metric_name or "").strip().lower()
    if is_test_like_path(path):
        return "Reduce test file sprawl: split fixtures/builders and isolate scenario matrices."
    if metric == "module_lines":
        return "Split oversized module into focused submodules with explicit ownership boundaries."
    if metric == "cyclomatic_complexity":
        return "Extract high-branch paths into helpers and flatten decision logic."
    if metric in {"class_public_methods", "class_instance_attributes"}:
        return "Reduce class surface area: split responsibilities into cohesive collaborators."
    if metric in {"line_length_hard_hits", "line_length_soft_hits"}:
        return "Refactor dense statements into named helpers to improve readability and reviewability."
    return "Split high-complexity logic and restore module boundaries."


def _sample_bonus(metric: str, severity: str) -> float:
    if metric == "cyclomatic_complexity":
        return 6.0 if severity == "critical" else 2.0 if severity == "warning" else 0.0
    if metric == "module_lines":
        return 3.0 if severity == "critical" else 1.5 if severity == "warning" else 0.0
    return 0.0


def sample_metric_bonus(item: dict[str, Any]) -> float:
    samples = item.get("samples", [])
    if not isinstance(samples, list):
        return 0.0
    bonus = 0.0
    for sample in samples:
        if not isinstance(sample, dict):
            continue
        metric = str(sample.get("metric", "") or "").strip().lower()
        severity = str(sample.get("severity", "") or "").strip().lower()
        bonus += _sample_bonus(metric, severity)
    return round(bonus, 2)


def rank_breakdown(
    item: dict[str, Any],
    *,
    is_test_like_path,
    is_doc_like_path,
) -> tuple[float, dict[str, float]]:
    path = str(item.get("path", "") or "")
    critical = int(item.get("critical", 0))
    warning = int(item.get("warning", 0))
    hotspot_score = float(item.get("hotspot_score", 0.0))
    comp_score_value = item.get("component_score")
    comp_penalty = 0.0
    if isinstance(comp_score_value, (int, float)):
        comp_penalty = max(0.0, (70.0 - float(comp_score_value)) * 0.3)
    priority_boost = 5.0 if str(item.get("priority", "")) == "high" else 0.0
    test_penalty = 12.0 if is_test_like_path(path) else 0.0
    docs_penalty = 6.0 if is_doc_like_path(path) else 0.0
    metric_bonus = sample_metric_bonus(item)
    base_signal = hotspot_score + critical * 8.0 + warning * 2.0
    rank_score = base_signal + metric_bonus + comp_penalty + priority_boost - test_penalty - docs_penalty
    breakdown = {
        "base_signal": round(base_signal, 2),
        "metric_bonus": round(metric_bonus, 2),
        "hotspot_score": round(hotspot_score, 2),
        "critical_bonus": round(critical * 8.0, 2),
        "warning_bonus": round(warning * 2.0, 2),
        "component_penalty": round(comp_penalty, 2),
        "priority_boost": round(priority_boost, 2),
        "test_penalty": round(test_penalty, 2),
        "docs_penalty": round(docs_penalty, 2),
    }
    return rank_score, breakdown


def ranked_items(
    by_path: dict[str, dict[str, Any]],
    *,
    is_test_like_path,
    is_doc_like_path,
) -> list[tuple[float, dict[str, Any], dict[str, float]]]:
    ranked: list[tuple[float, dict[str, Any], dict[str, float]]] = []
    for item in by_path.values():
        rank_score, breakdown = rank_breakdown(
            item,
            is_test_like_path=is_test_like_path,
            is_doc_like_path=is_doc_like_path,
        )
        ranked.append((rank_score, item, breakdown))
    ranked.sort(key=lambda x: (-x[0], x[1].get("path", "")))
    return ranked


def top_items(
    ranked: list[tuple[float, dict[str, Any], dict[str, float]]],
    *,
    limit: int,
    is_test_like_path,
    is_doc_like_path,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for idx, (rank_score, item, breakdown) in enumerate(ranked[:limit], start=1):
        component_score = item.get("component_score")
        path = str(item.get("path", "") or "")
        dominant = dominant_metric(item)
        items.append(
            {
                "rank": idx,
                "path": path,
                "component": item.get("component", ""),
                "critical": int(item.get("critical", 0)),
                "warning": int(item.get("warning", 0)),
                "hotspot_score": round(float(item.get("hotspot_score", 0.0)), 2),
                "component_score": (
                    round(float(component_score), 2)
                    if isinstance(component_score, (int, float))
                    else None
                ),
                "priority": str(item.get("priority", "")),
                "rank_score": round(rank_score, 2),
                "rank_breakdown": breakdown,
                "dominant_metric": dominant,
                "fix_hint": fix_hint(
                    path=path,
                    dominant_metric_name=dominant,
                    is_test_like_path=is_test_like_path,
                    is_doc_like_path=is_doc_like_path,
                ),
            }
        )
    return items
