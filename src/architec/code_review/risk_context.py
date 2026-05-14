from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from architec.support.io_utils import normalize_relpath


LOW_COVERAGE_THRESHOLD = 0.6
HIGH_CHURN_THRESHOLD = 10
HIGH_COMPLEXITY_THRESHOLD = 15
RECURRING_HISTORY_THRESHOLD = 2


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _normal_path(path: object) -> str:
    text = normalize_relpath(str(path or ""))
    while text.startswith("./"):
        text = text[2:]
    return text.strip("/")


def _number(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coverage_value(value: object) -> float | None:
    raw = value
    if isinstance(value, dict):
        for key in ("line_rate", "coverage", "percent", "rate"):
            if key in value:
                raw = value.get(key)
                break
    number = _number(raw)
    if number is None:
        return None
    if number > 1.0:
        number = number / 100.0
    if number < 0.0:
        return None
    return min(number, 1.0)


def _churn_value(value: object) -> int | None:
    raw = value
    if isinstance(value, dict):
        for key in ("changes", "commit_count", "count", "churn"):
            if key in value:
                raw = value.get(key)
                break
    number = _number(raw)
    if number is None or number < 0:
        return None
    return int(number)


def _complexity_value(value: object) -> float | None:
    raw = value
    if isinstance(value, dict):
        for key in ("complexity", "cyclomatic", "score"):
            if key in value:
                raw = value.get(key)
                break
    number = _number(raw)
    if number is None or number < 0:
        return None
    return number


def _recurrence_value(value: object) -> int | None:
    raw = value
    if isinstance(value, dict):
        for key in ("count", "occurrences", "recurrence", "recent_count"):
            if key in value:
                raw = value.get(key)
                break
    number = _number(raw)
    if number is None or number < 0:
        return None
    return int(number)


def _format_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _coverage_by_file(context: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    raw = _dict(context.get("coverage_by_file"))
    for path, value in raw.items():
        normalized = _normal_path(path)
        coverage = _coverage_value(value)
        if normalized and coverage is not None:
            out[normalized] = round(coverage, 4)
    return out


def _churn_by_file(context: dict[str, Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    raw = _dict(context.get("churn_by_file"))
    for path, value in raw.items():
        normalized = _normal_path(path)
        churn = _churn_value(value)
        if normalized and churn is not None:
            out[normalized] = churn
    return out


def _complexity_by_file(context: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    raw = _dict(context.get("complexity_by_file"))
    for path, value in raw.items():
        normalized = _normal_path(path)
        complexity = _complexity_value(value)
        if normalized and complexity is not None:
            out[normalized] = round(complexity, 4)
    return out


def _public_api_files(context: dict[str, Any]) -> set[str]:
    raw = context.get("public_api_files")
    out: set[str] = set()
    if isinstance(raw, list):
        for item in raw:
            normalized = _normal_path(item)
            if normalized:
                out.add(normalized)
    elif isinstance(raw, dict):
        for path, value in raw.items():
            if not value and not isinstance(value, dict):
                continue
            normalized = _normal_path(path)
            if normalized:
                out.add(normalized)
    return out


def _historical_recurrence_by_file(context: dict[str, Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    raw = _dict(context.get("historical_recurrence_by_file"))
    for path, value in raw.items():
        normalized = _normal_path(path)
        recurrence = _recurrence_value(value)
        if normalized and recurrence is not None:
            out[normalized] = recurrence
    return out


def _test_map(context: dict[str, Any]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    raw = _dict(context.get("test_files_by_source"))
    for path, values in raw.items():
        normalized = _normal_path(path)
        if not normalized:
            continue
        tests = [_normal_path(item) for item in _list(values)]
        out[normalized] = [item for item in tests if item]
    return out


def _changed_tests(context: dict[str, Any]) -> list[str]:
    raw = _list(context.get("changed_tests")) or _list(context.get("changed_test_files"))
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        path = _normal_path(item)
        if not path or path in seen:
            continue
        seen.add(path)
        out.append(path)
    return out


def load_risk_context(path: str | Path) -> dict[str, Any]:
    context_path = Path(path)
    try:
        loaded = json.loads(context_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Risk context JSON not found: {context_path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid risk context JSON: {context_path}: {exc.msg}") from exc
    except OSError as exc:
        raise RuntimeError(f"Unable to read risk context JSON: {context_path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise RuntimeError(f"Risk context JSON must be an object: {context_path}")
    return loaded


def _concern_path(concern: dict[str, Any]) -> str:
    location = _dict(concern.get("location"))
    return _normal_path(location.get("path", ""))


def _copy_concern(concern: dict[str, Any]) -> dict[str, Any]:
    copied = dict(concern)
    copied["evidence"] = [str(item) for item in _list(concern.get("evidence"))]
    copied["blast_radius"] = [str(item) for item in _list(concern.get("blast_radius"))]
    if "references" in concern:
        copied["references"] = [dict(item) if isinstance(item, dict) else item for item in _list(concern.get("references"))]
    return copied


def apply_risk_context(
    concerns: list[dict[str, Any]],
    context: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if context is None:
        return concerns, {}
    coverage = _coverage_by_file(context)
    churn = _churn_by_file(context)
    complexity = _complexity_by_file(context)
    public_api = _public_api_files(context)
    recurrence = _historical_recurrence_by_file(context)
    tests_by_source = _test_map(context)
    changed_tests = _changed_tests(context)
    enriched: list[dict[str, Any]] = []
    by_factor = {
        "low_coverage": 0,
        "high_churn": 0,
        "high_complexity": 0,
        "public_api": 0,
        "recurring_history": 0,
        "missing_related_tests": 0,
    }
    enriched_total = 0
    for concern in concerns:
        path = _concern_path(concern)
        copied = _copy_concern(concern)
        facts: list[str] = []
        if path in coverage:
            value = coverage[path]
            facts.append(f"risk_context.coverage={value:.2f}")
            if value < LOW_COVERAGE_THRESHOLD:
                facts.append("risk_context.coverage_level=low")
                by_factor["low_coverage"] += 1
        if path in churn:
            value = churn[path]
            facts.append(f"risk_context.churn={value}")
            if value >= HIGH_CHURN_THRESHOLD:
                facts.append("risk_context.churn_level=high")
                by_factor["high_churn"] += 1
        if path in complexity:
            value = complexity[path]
            facts.append(f"risk_context.complexity={_format_number(value)}")
            if value >= HIGH_COMPLEXITY_THRESHOLD:
                facts.append("risk_context.complexity_level=high")
                by_factor["high_complexity"] += 1
        if path in public_api:
            facts.append("risk_context.public_api=true")
            by_factor["public_api"] += 1
        if path in recurrence:
            value = recurrence[path]
            facts.append(f"risk_context.recurrence={value}")
            if value >= RECURRING_HISTORY_THRESHOLD:
                facts.append("risk_context.recurrence_level=recurring")
                by_factor["recurring_history"] += 1
        if path in tests_by_source:
            related_tests = tests_by_source[path]
            facts.append(f"risk_context.related_test_total={len(related_tests)}")
            if not related_tests:
                facts.append("risk_context.related_tests=none")
                by_factor["missing_related_tests"] += 1
        if facts:
            copied["evidence"].extend(facts)
            enriched_total += 1
        enriched.append(copied)

    file_paths = set(coverage) | set(churn) | set(complexity) | set(public_api) | set(recurrence) | set(tests_by_source)
    scan = {
        "input_file_total": len(file_paths),
        "changed_test_total": len(changed_tests),
        "enriched_concern_total": enriched_total,
        "by_factor": {key: value for key, value in sorted(by_factor.items()) if value},
        "coverage_file_total": len(coverage),
        "churn_file_total": len(churn),
        "complexity_file_total": len(complexity),
        "public_api_file_total": len(public_api),
        "recurrence_file_total": len(recurrence),
        "test_map_file_total": len(tests_by_source),
    }
    return enriched, scan


__all__ = [
    "apply_risk_context",
    "load_risk_context",
]
