from __future__ import annotations

from pathlib import Path
from typing import Any

from architec.integration.paths import (
    BASELINE_JSON_PATH,
    GATE_JSON_PATH,
    GATE_SUMMARY_MD_PATH,
)
from architec.support.io_utils import read_json, utc_now_iso, write_json

_CATEGORY_SEVERITY = {
    "fallback_branch": "block",
    "legacy_impl": "block",
    "compat_layer": "block",
    "obsolete_script": "warn",
    "stale_doc": "warn",
    "stale_config": "warn",
    "stale_prompt": "warn",
}


def _report_section(report: dict[str, Any], key: str, expected_type: type) -> Any:
    value = report.get(key, expected_type())
    return value if isinstance(value, expected_type) else expected_type()


def load_baseline_snapshot(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    baseline_path = root / BASELINE_JSON_PATH
    if not baseline_path.is_file():
        raise FileNotFoundError(
            f"Baseline not found at {baseline_path}. Run `archi status --snapshot` to capture current advisory state."
        )
    baseline = read_json(baseline_path, {})
    if not isinstance(baseline, dict) or not baseline:
        raise RuntimeError(f"Baseline file at {baseline_path} is empty or invalid.")
    return baseline


def _compare_scores(
    current_scores: dict[str, Any],
    baseline_scores: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for key, label in (
        ("overall", "overall score"),
        ("structure", "structure score"),
        ("full", "full score"),
    ):
        current = current_scores.get(key)
        baseline = baseline_scores.get(key)
        if current is None or baseline is None:
            continue
        passed = float(current) >= float(baseline)
        check = {
            "kind": "score",
            "name": label,
            "metric": key,
            "severity": "block",
            "current": current,
            "baseline": baseline,
            "passed": passed,
        }
        checks.append(check)
        if not passed:
            failures.append(check)
    return checks, failures, []


def _compare_cleanup_totals(
    current_cleanup: dict[str, Any],
    baseline_cleanup: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for key, label in (
        ("candidate_total", "cleanup candidate total"),
        ("review_required_total", "cleanup review-required total"),
    ):
        current = int(current_cleanup.get(key, 0) or 0)
        baseline = int(baseline_cleanup.get(key, 0) or 0)
        passed = current <= baseline
        check = {
            "kind": "cleanup_total",
            "name": label,
            "metric": key,
            "severity": "warn",
            "current": current,
            "baseline": baseline,
            "passed": passed,
        }
        checks.append(check)
        if not passed:
            warnings.append(check)
    return checks, [], warnings


def _category_severity(category: str) -> str:
    normalized = str(category or "").strip()
    if not normalized:
        return "block"
    return _CATEGORY_SEVERITY.get(normalized, "block")


def _compare_cleanup_categories(
    current_cleanup: dict[str, Any],
    baseline_cleanup: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    current = (
        current_cleanup.get("by_category", {})
        if isinstance(current_cleanup.get("by_category"), dict)
        else {}
    )
    baseline = (
        baseline_cleanup.get("by_category", {})
        if isinstance(baseline_cleanup.get("by_category"), dict)
        else {}
    )
    keys = sorted(set(current) | set(baseline))
    for key in keys:
        current_value = int(current.get(key, 0) or 0)
        baseline_value = int(baseline.get(key, 0) or 0)
        passed = current_value <= baseline_value
        severity = _category_severity(key)
        check = {
            "kind": "cleanup_category",
            "name": f"cleanup category {key}",
            "metric": key,
            "severity": severity,
            "current": current_value,
            "baseline": baseline_value,
            "passed": passed,
        }
        checks.append(check)
        if not passed:
            if severity == "warn":
                warnings.append(check)
            else:
                failures.append(check)
    return checks, failures, warnings


def build_gate_result(
    *,
    current_report: dict[str, Any],
    baseline: dict[str, Any],
) -> dict[str, Any]:
    current_scores = _report_section(current_report, "scores", dict)
    current_cleanup = _report_section(current_report, "cleanup", dict)
    baseline_meta = _report_section(baseline, "meta", dict)
    baseline_scores = _report_section(baseline, "scores", dict)
    baseline_cleanup = _report_section(baseline, "cleanup", dict)

    checks: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for compare in (
        _compare_scores,
        _compare_cleanup_totals,
        _compare_cleanup_categories,
    ):
        new_checks, new_failures, new_warnings = compare(
            current_scores if compare is _compare_scores else current_cleanup,
            baseline_scores if compare is _compare_scores else baseline_cleanup,
        )
        checks.extend(new_checks)
        failures.extend(new_failures)
        warnings.extend(new_warnings)

    status = "fail" if failures else ("warn" if warnings else "pass")
    return {
        "generated_at": utc_now_iso(),
        "passed": not failures,
        "status": status,
        "baseline_generated_at": str(baseline_meta.get("generated_at", "") or ""),
        "baseline_source_mode": str(baseline_meta.get("source_mode", "") or ""),
        "baseline_path": str(baseline_meta.get("path", "") or ""),
        "check_total": len(checks),
        "failure_total": len(failures),
        "warning_total": len(warnings),
        "checks": checks,
        "failures": failures,
        "warnings": warnings,
    }


def render_gate_summary(result: dict[str, Any]) -> str:
    gate = _report_section(result, "gate", dict)
    scores = _report_section(result, "scores", dict)
    cleanup = _report_section(result, "cleanup", dict)
    failures = gate.get("failures", []) if isinstance(gate.get("failures"), list) else []
    warnings = gate.get("warnings", []) if isinstance(gate.get("warnings"), list) else []
    checks = gate.get("checks", []) if isinstance(gate.get("checks"), list) else []

    lines = [
        "# Architec Gate",
        "",
        f"- Generated At: `{gate.get('generated_at', '')}`",
        f"- Status: `{gate.get('status', '')}`",
        f"- Baseline Generated At: `{gate.get('baseline_generated_at', '')}`",
        f"- Checks: `{gate.get('check_total', 0)}`",
        f"- Failures: `{gate.get('failure_total', 0)}`",
        f"- Warnings: `{gate.get('warning_total', 0)}`",
        "",
        "## Current Snapshot",
        f"- Overall: `{scores.get('overall', 0.0)}`",
        f"- Structure: `{scores.get('structure', 0.0)}`",
        f"- Full: `{scores.get('full', 0.0)}`",
        f"- Cleanup Candidates: `{cleanup.get('candidate_total', 0)}`",
        f"- Cleanup Review Required: `{cleanup.get('review_required_total', 0)}`",
        "",
        "## Gate Findings",
    ]
    if not failures and not warnings:
        lines.append("- All configured baseline regression checks passed.")
    for item in failures:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- BLOCK `{item.get('name', '')}` failed: current=`{item.get('current', '')}` "
            f"baseline=`{item.get('baseline', '')}`"
        )
    for item in warnings:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- WARN `{item.get('name', '')}` regressed: current=`{item.get('current', '')}` "
            f"baseline=`{item.get('baseline', '')}`"
        )
    lines.extend(["", "## Gate Checks"])
    for item in checks[:12]:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- `{item.get('name', '')}` | current=`{item.get('current', '')}` | "
            f"baseline=`{item.get('baseline', '')}` | severity=`{item.get('severity', '')}` | "
            f"passed=`{item.get('passed', False)}`"
        )
    return "\n".join(lines).rstrip() + "\n"


def write_gate_artifacts(root: Path, result: dict[str, Any]) -> dict[str, str]:
    json_path = root / GATE_JSON_PATH
    summary_path = root / GATE_SUMMARY_MD_PATH
    write_json(json_path, result)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(render_gate_summary(result), encoding="utf-8")
    return {
        "gate_json": str(json_path),
        "gate_summary_md": str(summary_path),
    }


__all__ = [
    "build_gate_result",
    "load_baseline_snapshot",
    "render_gate_summary",
    "write_gate_artifacts",
]
