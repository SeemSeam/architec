from __future__ import annotations

from pathlib import Path
from typing import Any

from architec.backend_llm import complete_json
from architec.support.io_utils import utc_now_iso
from architec.integration.resource_paths import resolve_config_file


def llm_history_enhancement(
    project_root: Path,
    summary: dict[str, Any],
    hotspots: list[dict[str, Any]],
) -> dict[str, Any] | None:
    compact_hotspots = [
        {
            "path": item.get("path", ""),
            "critical": item.get("critical", 0),
            "warning": item.get("warning", 0),
            "score": item.get("score", 0),
        }
        for item in hotspots[:8]
    ]
    payload = {"summary": summary, "hotspots": compact_hotspots}
    prompt = f"Input:\n{payload}"
    return complete_json(
        project_root,
        task="architect_history",
        tier="strong",
        prompt=prompt,
        timeout_sec=20.0,
        max_tokens=500,
    )


def build_debt_ledger(
    *,
    summary: dict[str, Any],
    current_issues: dict[str, Any],
    prev_issues: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    current_keys = set(current_issues.keys())
    prev_keys = set(prev_issues.keys())
    new_issue_keys = sorted(current_keys - prev_keys)
    resolved_issue_keys = sorted(prev_keys - current_keys)
    ledger = {
        "generated_at": utc_now_iso(),
        "summary": summary,
        "counts": {
            "current_open": len(current_keys),
            "new_since_last": len(new_issue_keys),
            "resolved_since_last": len(resolved_issue_keys),
        },
        "issues": current_issues,
        "delta": {
            "new_issue_keys": new_issue_keys[:200],
            "resolved_issue_keys": resolved_issue_keys[:200],
        },
    }
    return ledger, dict(ledger["counts"])


def build_history_report(
    *,
    root: Path,
    summary: dict[str, Any],
    full_score: dict[str, Any],
    hotspots: list[dict[str, Any]],
    component_risk: list[dict[str, Any]],
    component_debt: list[dict[str, Any]],
    descriptor_count: int,
    iterative_plan: dict[str, list[dict[str, Any]]],
    ledger_path: Path,
    ledger_delta: dict[str, Any],
    baseline_scores: dict[str, Any],
) -> dict[str, Any]:
    return {
        "generated_at": utc_now_iso(),
        "scope": "first-party source only",
        "baseline_scores": baseline_scores,
        "full_score": full_score,
        "summary": summary,
        "hotspots": hotspots,
        "component_risk": component_risk,
        "component_debt": component_debt,
        "descriptor_count": descriptor_count,
        "iterative_plan": iterative_plan,
        "debt_ledger": {"path": str(ledger_path), **ledger_delta},
        "policy": {
            "history_fix_mode": "baseline + no-regression on touched files",
            "blocking_rule": "new critical findings in touched files",
            "advice": "Use P0 for critical hotspots, P1 for boundary restore, P2 for governance.",
            "scoring_policy": str(resolve_config_file(root, "scoring-policy.json")),
        },
    }
