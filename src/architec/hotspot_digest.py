from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .io_utils import utc_now_iso, write_json
from .paths import HOTSPOT_DIGEST_PATH


def _topk_limit(default: int = 8) -> int:
    raw = str(os.environ.get("ARCH_HOTSPOT_TOPK", "") or "").strip()
    if not raw:
        return default
    try:
        return max(1, min(20, int(raw)))
    except Exception:
        return default


def _is_test_like_path(path: str) -> bool:
    rel = str(path or "").strip().replace("\\", "/").lower()
    if not rel:
        return False
    marker = f"/{rel}/"
    if "/tests/" in marker:
        return True
    name = Path(rel).name
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or name.endswith("_spec.py")
    )


def _is_doc_like_path(path: str) -> bool:
    rel = str(path or "").strip().replace("\\", "/").lower()
    if not rel:
        return False
    if rel.endswith(".md") or rel.endswith(".rst") or rel.endswith(".txt"):
        return True
    return rel.startswith("docs/") or "/docs/" in f"/{rel}/"


def _dominant_metric(item: dict[str, Any]) -> str:
    top_metrics = item.get("top_metrics", {})
    if isinstance(top_metrics, dict) and top_metrics:
        best = max(top_metrics.items(), key=lambda kv: float(kv[1] or 0.0))[0]
        return str(best or "")
    if int(item.get("critical", 0) or 0) > 0:
        return "cyclomatic_complexity"
    if int(item.get("warning", 0) or 0) > 0:
        return "module_lines"
    return "unknown"


def _fix_hint(*, path: str, dominant_metric: str) -> str:
    metric = str(dominant_metric or "").strip().lower()
    if _is_test_like_path(path):
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


def _sample_metric_bonus(item: dict[str, Any]) -> float:
    samples = item.get("samples", [])
    if not isinstance(samples, list):
        return 0.0
    bonus = 0.0
    for sample in samples:
        if not isinstance(sample, dict):
            continue
        metric = str(sample.get("metric", "") or "").strip().lower()
        severity = str(sample.get("severity", "") or "").strip().lower()
        if metric == "cyclomatic_complexity":
            if severity == "critical":
                bonus += 6.0
            elif severity == "warning":
                bonus += 2.0
        elif metric == "module_lines":
            if severity == "critical":
                bonus += 3.0
            elif severity == "warning":
                bonus += 1.5
    return round(bonus, 2)


def build_hotspot_digest(
    root: Path,
    *,
    history: dict[str, Any],
    score: dict[str, Any],
    batches: list[dict[str, Any]],
    governance: dict[str, Any],
    topk: int | None = None,
) -> dict[str, Any]:
    limit = max(1, min(20, int(topk or _topk_limit())))
    by_path: dict[str, dict[str, Any]] = {}

    hotspots = history.get("hotspots", []) if isinstance(history.get("hotspots"), list) else []
    for item in hotspots:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "") or "").strip()
        if not path:
            continue
        by_path[path] = {
            "path": path,
            "component": "",
            "critical": int(item.get("critical", 0) or 0),
            "warning": int(item.get("warning", 0) or 0),
            "hotspot_score": float(item.get("score", 0.0) or 0.0),
            "component_score": None,
            "priority": "",
            "samples": item.get("samples", []) if isinstance(item.get("samples", []), list) else [],
            "top_metrics": (
                dict(item.get("top_metrics", {}))
                if isinstance(item.get("top_metrics"), dict)
                else {}
            ),
        }

    components = score.get("components", []) if isinstance(score.get("components"), list) else []
    for comp in components:
        if not isinstance(comp, dict):
            continue
        component = str(comp.get("component", "") or "")
        comp_score = float(comp.get("score", 100.0) or 100.0)
        refs = comp.get("hotspot_refs", []) if isinstance(comp.get("hotspot_refs"), list) else []
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            path = str(ref.get("path", "") or "").strip()
            if not path:
                continue
            slot = by_path.setdefault(
                path,
                {
                    "path": path,
                    "component": component,
                    "critical": 0,
                    "warning": 0,
                    "hotspot_score": 0.0,
                    "component_score": None,
                    "priority": "",
                    "samples": [],
                    "top_metrics": {},
                },
            )
            slot["component"] = slot.get("component") or component
            existing = slot.get("component_score")
            if isinstance(existing, (int, float)):
                slot["component_score"] = min(float(existing), comp_score)
            else:
                slot["component_score"] = comp_score
            slot["critical"] = max(int(slot.get("critical", 0)), int(ref.get("critical", 0) or 0))
            slot["warning"] = max(int(slot.get("warning", 0)), int(ref.get("warning", 0) or 0))
            slot["hotspot_score"] = max(float(slot.get("hotspot_score", 0.0)), float(ref.get("score", 0.0) or 0.0))

    for batch in batches:
        if not isinstance(batch, dict):
            continue
        prio = str(batch.get("priority", "") or "")
        component = str(batch.get("component", "") or "")
        files = batch.get("focus_files", []) if isinstance(batch.get("focus_files"), list) else []
        for path in files:
            p = str(path or "").strip()
            if not p:
                continue
            slot = by_path.setdefault(
                p,
                {
                    "path": p,
                    "component": component,
                    "critical": 0,
                    "warning": 0,
                    "hotspot_score": 0.0,
                    "component_score": None,
                    "priority": prio,
                    "samples": [],
                    "top_metrics": {},
                },
            )
            if prio and not slot.get("priority"):
                slot["priority"] = prio
            if component and not slot.get("component"):
                slot["component"] = component

    ranked = []
    for item in by_path.values():
        path = str(item.get("path", "") or "")
        critical = int(item.get("critical", 0))
        warning = int(item.get("warning", 0))
        hs = float(item.get("hotspot_score", 0.0))
        comp_score_value = item.get("component_score")
        comp_penalty = 0.0
        if isinstance(comp_score_value, (int, float)):
            comp_penalty = max(0.0, (70.0 - float(comp_score_value)) * 0.3)
        pboost = 5.0 if str(item.get("priority", "")) == "high" else 0.0
        test_penalty = 12.0 if _is_test_like_path(path) else 0.0
        docs_penalty = 6.0 if _is_doc_like_path(path) else 0.0
        metric_bonus = _sample_metric_bonus(item)
        base_signal = hs + critical * 8.0 + warning * 2.0
        rank_score = base_signal + metric_bonus + comp_penalty + pboost - test_penalty - docs_penalty
        breakdown = {
            "base_signal": round(base_signal, 2),
            "metric_bonus": round(metric_bonus, 2),
            "hotspot_score": round(hs, 2),
            "critical_bonus": round(critical * 8.0, 2),
            "warning_bonus": round(warning * 2.0, 2),
            "component_penalty": round(comp_penalty, 2),
            "priority_boost": round(pboost, 2),
            "test_penalty": round(test_penalty, 2),
            "docs_penalty": round(docs_penalty, 2),
        }
        ranked.append((rank_score, item, breakdown))

    ranked.sort(key=lambda x: (-x[0], x[1].get("path", "")))
    top_items = []
    for idx, (rank_score, item, breakdown) in enumerate(ranked[:limit], start=1):
        component_score = item.get("component_score")
        path = str(item.get("path", "") or "")
        dominant = _dominant_metric(item)
        top_items.append(
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
                "fix_hint": _fix_hint(path=path, dominant_metric=dominant),
            }
        )

    payload = {
        "generated_at": utc_now_iso(),
        "topk": limit,
        "scores": governance,
        "items": top_items,
    }
    write_json(root / HOTSPOT_DIGEST_PATH, payload)
    return payload
