from __future__ import annotations

from pathlib import Path
from typing import Any

from architec.descriptors.public import load_or_build_component_descriptors
from architec.scoring.contract_engine import (
    aggregate_hotspots,
    build_component_risk,
    issue_catalog,
    summarize_findings,
)
from architec.integration.hippo_adapter import HippoSnapshot
from architec.support.io_utils import read_json, write_json
from architec.analysis.history_analyzer_report import (
    build_debt_ledger,
    build_history_report,
    llm_history_enhancement,
)
from architec.support.llm_guard import guard_llm_result
from architec.integration.paths import DEBT_LEDGER_PATH, HISTORY_REPORT_PATH
from architec.scoring.public import evaluate_full_score, load_scoring_policy


def _finding_counts(descriptor: dict[str, Any]) -> tuple[int, int]:
    findings = (
        descriptor.get("findings_by_severity", {})
        if isinstance(descriptor, dict)
        else {}
    )
    return (
        int(findings.get("critical", 0) or 0),
        int(findings.get("warning", 0) or 0),
    )


def _hotspot_paths(descriptor: dict[str, Any]) -> list[str]:
    return [
        str(item.get("path", "") or "")
        for item in descriptor.get("top_hotspots", [])[:4]
        if isinstance(item, dict)
    ]


def _component_debt_item(
    component: str,
    descriptor: dict[str, Any],
) -> dict[str, Any] | None:
    critical, warning = _finding_counts(descriptor)
    if critical <= 0 and warning <= 0:
        return None
    return {
        "component": component,
        "layer_role": str(descriptor.get("layer_role", "") or ""),
        "critical": critical,
        "warning": warning,
        "confidence": float(descriptor.get("confidence", 0.0) or 0.0),
        "responsibility_summary": str(
            descriptor.get("responsibility_summary", "") or ""
        ),
        "hotspot_paths": _hotspot_paths(descriptor),
    }


def _component_debt_view(
    descriptors: dict[str, dict[str, Any]],
    *,
    limit: int = 12,
) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for component, descriptor in descriptors.items():
        item = _component_debt_item(component, descriptor)
        if item is not None:
            ranked.append(item)
    ranked.sort(
        key=lambda item: (
            -int(item.get("critical", 0) or 0),
            -int(item.get("warning", 0) or 0),
            -float(item.get("confidence", 0.0) or 0.0),
            str(item.get("component", "") or ""),
        )
    )
    return ranked[: max(1, limit)]


def _derive_iterative_plan(
    hotspots: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
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
                (
                    "Split high-branch functions into helper units "
                    "with narrow responsibilities."
                ),
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


def analyze_history_and_iterate(
    project_root: str | Path,
    *,
    llm_enabled: bool = True,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    snapshot = HippoSnapshot.load(root)
    descriptors = load_or_build_component_descriptors(
        root,
        snapshot=snapshot,
        persist=False,
    )
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

    ledger, ledger_delta = build_debt_ledger(
        summary=summary,
        current_issues=current_issues,
        prev_issues=prev_issues,
    )
    write_json(ledger_path, ledger)

    report = build_history_report(
        root=root,
        summary=summary,
        full_score=full_score,
        hotspots=hotspots,
        component_risk=component_risk,
        component_debt=_component_debt_view(descriptors, limit=12),
        descriptor_count=len(descriptors),
        iterative_plan=_derive_iterative_plan(hotspots),
        ledger_path=ledger_path,
        ledger_delta=ledger_delta,
        baseline_scores=snapshot.metrics.get("scores", {}),
    )
    if llm_enabled:
        llm_part = guard_llm_result(
            root,
            task="architect_history",
            runner=lambda: llm_history_enhancement(
                root,
                summary=summary,
                hotspots=hotspots,
            ),
        )
        report["llm_enhancement"] = llm_part

    write_json(root / HISTORY_REPORT_PATH, report)
    return report
