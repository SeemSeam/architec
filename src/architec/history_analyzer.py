from __future__ import annotations

from pathlib import Path
from typing import Any

from .backend_llm import complete_json
from .component_descriptors import load_or_build_component_descriptors
from .contract_engine import (
    aggregate_hotspots,
    build_component_risk,
    issue_catalog,
    summarize_findings,
)
from .hippo_adapter import HippoSnapshot
from .io_utils import read_json, utc_now_iso, write_json
from .llm_guard import guard_llm_result
from .paths import DEBT_LEDGER_PATH, HISTORY_REPORT_PATH
from .resource_paths import resolve_config_file
from .scoring_policy import evaluate_full_score, load_scoring_policy


def _component_debt_view(
    descriptors: dict[str, dict[str, Any]],
    *,
    limit: int = 12,
) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for component, descriptor in descriptors.items():
        findings = descriptor.get("findings_by_severity", {}) if isinstance(descriptor, dict) else {}
        critical = int(findings.get("critical", 0) or 0)
        warning = int(findings.get("warning", 0) or 0)
        if critical <= 0 and warning <= 0:
            continue
        ranked.append(
            {
                "component": component,
                "layer_role": str(descriptor.get("layer_role", "") or ""),
                "critical": critical,
                "warning": warning,
                "confidence": float(descriptor.get("confidence", 0.0) or 0.0),
                "responsibility_summary": str(
                    descriptor.get("responsibility_summary", "") or ""
                ),
                "hotspot_paths": [
                    str(item.get("path", "") or "")
                    for item in descriptor.get("top_hotspots", [])[:4]
                    if isinstance(item, dict)
                ],
            }
        )
    ranked.sort(
        key=lambda item: (
            -int(item.get("critical", 0) or 0),
            -int(item.get("warning", 0) or 0),
            -float(item.get("confidence", 0.0) or 0.0),
            str(item.get("component", "") or ""),
        )
    )
    return ranked[: max(1, limit)]


def _derive_iterative_plan(hotspots: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    p0: list[dict[str, Any]] = []
    p1: list[dict[str, Any]] = []
    p2: list[dict[str, Any]] = []

    for spot in hotspots:
        item = {
            "path": spot["path"],
            "why": (
                f"critical={spot.get('critical', 0)}, "
                f"warning={spot.get('warning', 0)}, score={spot.get('score', 0)}"
            ),
            "suggested_actions": [
                "Split high-branch functions into helper units with narrow responsibilities.",
                "Keep behavior stable with characterization tests before refactor.",
                "Move cross-cutting logic behind explicit interfaces.",
            ],
        }
        if int(spot.get("critical", 0)) > 0 and len(p0) < 8:
            p0.append(item)
        elif len(p1) < 10:
            p1.append(item)
        else:
            p2.append(item)

    if not p2:
        p2.append(
            {
                "path": "governance",
                "why": "Sustain architecture quality after hotspot cleanup.",
                "suggested_actions": [
                    "Enforce no-regression policy on touched hotspot files.",
                    "Use complexity and module-size gates in CI for changed files.",
                    "Re-run architect baseline each iteration and compare deltas.",
                ],
            }
        )

    return {"P0": p0, "P1": p1, "P2": p2}


def _llm_history_enhancement(
    project_root: Path,
    summary: dict[str, Any],
    hotspots: list[dict[str, Any]],
) -> dict[str, Any] | None:
    compact_hotspots = [
        {
            "path": h.get("path", ""),
            "critical": h.get("critical", 0),
            "warning": h.get("warning", 0),
            "score": h.get("score", 0),
        }
        for h in hotspots[:8]
    ]
    payload = {
        "summary": summary,
        "hotspots": compact_hotspots,
    }
    prompt = (
        "You are an architecture remediation planner. "
        "Given first-party findings and hotspots, produce strict JSON only.\n\n"
        "Return schema:\n"
        "{\n"
        '  "executive_summary": "string",\n'
        '  "priority_order": [{"path":"string","reason":"string"}],\n'
        '  "quick_wins": ["string"],\n'
        '  "risk_watch": ["string"]\n'
        "}\n\n"
        f"Input:\n{payload}"
    )
    return complete_json(
        project_root,
        task="architect_history",
        tier="small",
        prompt=prompt,
        timeout_sec=20.0,
        max_tokens=500,
    )


def analyze_history_and_iterate(
    project_root: str | Path,
    *,
    llm_enabled: bool = True,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    snapshot = HippoSnapshot.load(root)
    descriptors = load_or_build_component_descriptors(root, snapshot=snapshot, persist=False)
    findings = snapshot.first_party_findings()

    summary = summarize_findings(findings)
    hotspots = aggregate_hotspots(findings, top_n=24)
    component_risk = build_component_risk(snapshot, findings)
    policy = load_scoring_policy(root)
    full_score = evaluate_full_score(
        summary=summary,
        baseline_scores=snapshot.metrics.get("scores", {})
        if isinstance(snapshot.metrics.get("scores", {}), dict)
        else {},
        policy=policy,
    )

    current_issues = issue_catalog(findings)
    ledger_path = root / DEBT_LEDGER_PATH
    prev_ledger = read_json(ledger_path, default={})
    prev_issues = prev_ledger.get("issues", {}) if isinstance(prev_ledger, dict) else {}
    if not isinstance(prev_issues, dict):
        prev_issues = {}

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
    write_json(ledger_path, ledger)

    report = {
        "generated_at": utc_now_iso(),
        "scope": "first-party source only",
        "baseline_scores": snapshot.metrics.get("scores", {}),
        "full_score": full_score,
        "summary": summary,
        "hotspots": hotspots,
        "component_risk": component_risk,
        "component_debt": _component_debt_view(descriptors, limit=12),
        "descriptor_count": len(descriptors),
        "iterative_plan": _derive_iterative_plan(hotspots),
        "debt_ledger": {
            "path": str(ledger_path),
            "current_open": len(current_keys),
            "new_since_last": len(new_issue_keys),
            "resolved_since_last": len(resolved_issue_keys),
        },
        "policy": {
            "history_fix_mode": "baseline + no-regression on touched files",
            "blocking_rule": "new critical findings in touched files",
            "advice": "Use P0 for critical hotspots, P1 for boundary restore, P2 for governance.",
            "scoring_policy": str(resolve_config_file(root, "scoring-policy.json")),
        },
    }
    if llm_enabled:
        llm_part = guard_llm_result(
            root,
            task="architect_history",
            runner=lambda: _llm_history_enhancement(
                root,
                summary=summary,
                hotspots=hotspots,
            ),
        )
        report["llm_enhancement"] = llm_part

    write_json(root / HISTORY_REPORT_PATH, report)
    return report
